import requests
from openai import OpenAI
from google import genai
from google.genai import types
from src.settings import settings
from src.utils import log


class MoltbookProvider:
    def __init__(self, llm_provider):
        self.llm_provider = llm_provider
        self.headers = {
            "Authorization": f"Bearer {settings.MOLTBOOK_API_KEY}",
            "Content-Type": "application/json",
        }
        self.timeout = settings.MOLTBOOK_API_TIMEOUT
        self.api_url = (
            settings.MOLTBOOK_BASE_URL
            if not settings.IS_TEST_MOLTBOOK_MODE
            else settings.MOCK_MOLTBOOK_BASE_URL
        )

    def _solve_cognitive_challenge(self, challenge: str, instructions: str = ""):
        use_gemini = settings.USE_GEMINI
        use_openrouter = settings.USE_OPENROUTER

        if not use_gemini and not use_openrouter and not self.llm_provider:
            log.error(
                "❌ No AI client (Ollama, Gemini or OpenRouter) available to solve challenge"
            )
            return None

        prompt = f"""You are solving a verification challenge on Moltbook to prove you're an AI agent.
Challenge: {challenge}
{f"Instructions: {instructions}" if instructions else ""}
CRITICAL RULES:
1. Respond with ONLY the answer - no explanation, no preamble
2. If it's a math problem, return only the number
3. If it's text cleanup, return only the cleaned text
4. Be precise and concise
Now solve the challenge above. Return ONLY the answer:
"""

        try:
            if use_gemini:
                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                try:
                    response = client.models.generate_content(
                        model=settings.GEMINI_MODEL_NAME,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.1),
                    )
                    answer = response.text.strip().split("\n")[0].strip()
                    log.info(f"💡 Challenge answer (Gemini): {answer}")
                    return answer
                except Exception as e:
                    log.error(f"❌ Gemini Challenge Error: {e}")
                    return None

            elif use_openrouter:
                openrouter_client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=settings.OPENROUTER_API_KEY,
                )
                for model in settings.FREE_MODELS:
                    log.debug(f"📡 [GATEWAY] Sending request to {model}...")
                    try:
                        response = openrouter_client.chat.completions.create(
                            model=model,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.1,
                        )
                        answer = (
                            response.choices[0]
                            .message.content.strip()
                            .split("\n")[0]
                            .strip()
                        )
                        answer = (
                            answer.replace("Answer:", "").replace("Result:", "").strip()
                        )
                        log.info(f"💡 Challenge answer (OpenRouter/{model}): {answer}")
                        return answer
                    except Exception as e:
                        if "429" in str(e):
                            log.warning(
                                f"⚠️ [RATE LIMIT] {model} is unavailable (429). Trying next model..."
                            )
                            continue
                        else:
                            log.error(f"❌ [ERROR] Request failed on {model}: {e}")
                            return None
                log.error("🔇 [FALLBACK EXHAUSTED] All models failed to respond.")
                return None

            else:
                response = self.llm_provider.client.chat(
                    model=settings.OLLAMA_MODEL or "qwen3:8b",
                    messages=[{"role": "user", "content": prompt}],
                    options={"temperature": 0.1},
                )
                answer = response["message"]["content"].strip()
                answer = answer.split("\n")[0].strip()
                answer = answer.replace("Answer:", "").replace("Result:", "").strip()
                log.info(f"💡 Challenge answer (Ollama): {answer}")
                return answer

        except Exception as e:
            log.error(f"❌ Error solving challenge: {e}")
            return None

    def _handle_verification(
        self, result: dict, original_endpoint: str, original_data: dict
    ):

        if not result.get("verification_required"):
            return result

        log.warning("🧩 Cognitive Challenge detected!")

        verification = result.get("verification", {})
        challenge_text = verification.get("challenge", "")
        instructions = verification.get("instructions", "")
        code = verification.get("code", "")

        if not challenge_text or not code:
            log.error("❌ Invalid verification format")
            return result

        log.info(f"📝 Challenge: {challenge_text}")
        if instructions:
            log.info(f"📋 Instructions: {instructions}")

        answer = self._solve_cognitive_challenge(challenge_text, instructions)

        if not answer:
            log.error("❌ Failed to solve challenge")
            return {"success": False, "error": "Challenge solving failed"}

        try:
            verify_url = f"{self.api_url}/verification/submit"
            verify_response = requests.post(
                verify_url,
                headers=self.headers,
                json={"code": code, "answer": answer},
                timeout=self.timeout,
            )

            verify_result = verify_response.json()

            if verify_result.get("success"):
                log.info("✅ Challenge solved successfully!")

                log.info("🔄 Retrying original request...")
                retry_response = requests.post(
                    original_endpoint,
                    headers=self.headers,
                    json=original_data,
                    timeout=self.timeout,
                )

                return self._handle_response(retry_response, original_endpoint)
            else:
                log.error(f"❌ Challenge verification failed: {verify_result}")
                return verify_result

        except Exception as e:
            log.error(f"❌ Error submitting challenge answer: {e}")
            return {"success": False, "error": str(e)}

    def register(self, name: str, description: str):
        try:
            url = f"{self.api_url}/agents/register"
            data = {"name": name, "description": description}
            response = requests.post(
                url, headers=self.headers, json=data, timeout=self.timeout
            )
            return response.json()
        except requests.exceptions.Timeout:
            log.error("Register request timeout")
            return {"success": False, "error": "Request timeout"}
        except requests.exceptions.RequestException as e:
            log.error(f"Register request failed: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            log.error(f"Register error: {e}")
            return {"success": False, "error": "Invalid response"}

    def get_me(self):
        try:
            url = f"{self.api_url}/agents/me"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            return self._handle_response(response, url)
        except requests.exceptions.Timeout:
            log.error("get_me request timeout")
            return None
        except Exception as e:
            log.error(f"get_me error: {e}")
            return None

    def update_profile(self, description: str):
        try:
            url = f"{self.api_url}/agents/me"
            data = {"description": description}
            response = requests.patch(
                url, headers=self.headers, json=data, timeout=self.timeout
            )
            return self._handle_response(response, url)
        except requests.exceptions.Timeout:
            log.error("update_profile request timeout")
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            log.error(f"update_profile error: {e}")
            return {"success": False, "error": "Invalid response"}

    def claim_status(self):
        try:
            url = f"{self.api_url}/agents/status"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            return self._handle_response(response, url)
        except requests.exceptions.Timeout:
            log.error("claim_status request timeout")
            return None
        except Exception as e:
            log.error(f"claim_status error: {e}")
            return None

    def view_another_agent_profile(self, name: str):
        try:
            url = f"{self.api_url}/agents/profile?name={name}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            return self._handle_response(response, url)
        except requests.exceptions.Timeout:
            log.error(f"view_another_agent_profile timeout for {name}")
            return None
        except Exception as e:
            log.error(f"view_another_agent_profile error: {e}")
            return None

    def create_text_post(self, title: str, content: str, submolt: str = "general"):
        try:
            url = f"{self.api_url}/posts"
            data = {"submolt": submolt, "title": title, "content": content}
            response = requests.post(
                url, headers=self.headers, json=data, timeout=self.timeout
            )

            result = self._handle_response(response, url)

            if result.get("verification_required"):
                return self._handle_verification(result, url, data)

            return result

        except requests.exceptions.Timeout:
            log.error("create_text_post request timeout")
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            log.error(f"create_text_post error: {e}")
            return {"success": False, "error": "Invalid response"}

    def create_link_post(self, title: str, url_to_share: str, submolt: str = "general"):
        try:
            url = f"{self.api_url}/posts"
            data = {"submolt": submolt, "title": title, "url": url_to_share}

            response = requests.post(
                url, headers=self.headers, json=data, timeout=self.timeout
            )

            result = self._handle_response(response, url)

            if result.get("verification_required"):
                return self._handle_verification(result, url, data)

            return result

        except requests.exceptions.Timeout:
            log.error("create_link_post request timeout")
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            log.error(f"create_link_post error: {e}")
            return {"success": False, "error": "Invalid response"}

    def get_posts(self, sort: str = "hot", limit: int = 25):
        try:
            url = f"{self.api_url}/posts?sort={sort}&limit={limit}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()

                if isinstance(data, dict):
                    if "posts" in data:
                        return {"success": True, "data": data["posts"]}
                    return {"success": True, "data": data}
                elif isinstance(data, list):
                    return {"success": True, "data": data}
            else:
                error_msg = (
                    response.json().get("error", "Unknown error")
                    if response.text
                    else "No response"
                )
                log.error(f"get_posts API error ({response.status_code}): {error_msg}")
                return {"success": False, "error": error_msg}

        except requests.exceptions.Timeout:
            log.error("get_posts request timeout")
            return {"success": False, "error": "Request timeout"}
        except requests.exceptions.RequestException as e:
            log.error(f"get_posts request failed: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            log.error(f"get_posts error: {e}")
            return {"success": False, "error": str(e)}

    def get_single_post(self, post_id: str):
        try:
            url = f"{self.api_url}/posts/{post_id}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            return self._handle_response(response, url)
        except requests.exceptions.Timeout:
            log.error(f"get_single_post timeout for {post_id}")
            return None
        except Exception as e:
            log.error(f"get_single_post error: {e}")
            return None

    def delete_post(self, post_id: str):
        try:
            url = f"{self.api_url}/posts/{post_id}"
            response = requests.delete(url, headers=self.headers, timeout=self.timeout)
            return self._handle_response(response, url)
        except requests.exceptions.Timeout:
            log.error(f"delete_post timeout for {post_id}")
            return None
        except Exception as e:
            log.error(f"delete_post error: {e}")
            return None

    def add_comment(self, post_id: str, content: str):
        try:
            url = f"{self.api_url}/posts/{post_id}/comments"
            data = {"content": content}
            response = requests.post(
                url, headers=self.headers, json=data, timeout=self.timeout
            )

            result = self._handle_response(response, url)

            if result.get("verification_required"):
                return self._handle_verification(result, url, data)

            return result

        except requests.exceptions.Timeout:
            log.error(f"add_comment timeout for post {post_id}")
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            log.error(f"add_comment error: {e}")
            return {"success": False, "error": str(e)}

    def reply_to_comment(self, post_id: str, content: str, parent_comment_id: str):
        try:
            url = f"{self.api_url}/posts/{post_id}/comments"
            data = {"content": content, "parent_id": parent_comment_id}

            log.info(f"   API CALL: reply_to_comment")
            log.info(f"   URL: {url}")
            log.info(f"   Payload: {data}")

            response = requests.post(
                url, headers=self.headers, json=data, timeout=self.timeout
            )

            result = self._handle_response(response, url)

            if result.get("verification_required"):
                return self._handle_verification(result, url, data)

            return result

        except Exception as e:
            log.error(f"reply_to_comment error: {e}")
            return {"success": False, "error": str(e)}

    def get_post_comments(self, post_id: str, sort: str = "top"):
        try:
            url = f"{self.api_url}/posts/{post_id}/comments?sort={sort}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()

                if isinstance(data, dict):
                    if "comments" in data:
                        return {"success": True, "data": data["comments"]}
                    return {"success": True, "data": data}
                elif isinstance(data, list):
                    return {"success": True, "data": data}
                return {"success": True, "data": []}
            else:
                return {"success": False, "error": f"API Error {response.status_code}"}

        except requests.exceptions.Timeout:
            log.error(f"get_post_comments timeout for post {post_id}")
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            log.error(f"get_post_comments error: {e}")
            return {"success": False, "error": str(e)}

    def vote(
        self, content_id: str, content_type: str = "posts", vote_type: str = "upvote"
    ):
        try:
            url = f"{self.api_url}/{content_type}/{content_id}/{vote_type}"
            response = requests.post(url, headers=self.headers, timeout=self.timeout)
            return self._handle_response(response, url)
        except requests.exceptions.Timeout:
            log.error(f"vote timeout for {content_type} {content_id}")
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            log.error(f"vote error: {e}")
            return {"success": False, "error": "Invalid response"}

    def create_submolt(self, name: str, display_name: str, description: str):
        try:
            url = f"{self.api_url}/submolts"
            data = {
                "name": name,
                "display_name": display_name,
                "description": description,
            }
            response = requests.post(
                url, json=data, headers=self.headers, timeout=self.timeout
            )
            return self._handle_response(response, url)
        except requests.exceptions.Timeout:
            log.error("create_submolt request timeout")
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            log.error(f"create_submolt error: {e}")
            return {"success": False, "error": "Invalid response"}

    def list_submolts(self):
        try:
            url = f"{self.api_url}/submolts"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()

                if isinstance(data, dict):
                    if "submolts" in data:
                        return {"success": True, "data": data["submolts"]}
                    return {"success": True, "data": data}
                elif isinstance(data, list):
                    return {"success": True, "data": data}
                return {"success": True, "data": []}
            else:
                return {"success": False, "error": f"API Error {response.status_code}"}

        except Exception as e:
            log.error(f"list_submolts error: {e}")
            return {"success": False, "error": str(e)}

    def get_submolt_info(self, submolt_name: str):
        try:
            url = f"{self.api_url}/submolts/{submolt_name}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            return None
        except requests.exceptions.Timeout:
            log.error(f"get_submolt_info timeout for {submolt_name}")
            return None
        except Exception as e:
            log.error(f"get_submolt_info error: {e}")
            return None

    def subscribe_submolt(self, submolt_name: str, subscribe_type: str = "subscribe"):
        try:
            url = f"{self.api_url}/submolts/{submolt_name}/{subscribe_type}"
            response = requests.post(url, headers=self.headers, timeout=self.timeout)
            return self._handle_response(response, url)
        except requests.exceptions.Timeout:
            log.error(f"subscribe_submolt timeout for {submolt_name}")
            return None
        except Exception as e:
            log.error(f"subscribe_submolt error: {e}")
            return None

    def follow_agent(self, agent_name: str, follow_type: str = "follow"):
        try:
            url = f"{self.api_url}/agents/{agent_name}/follow"

            if follow_type == "follow":
                response = requests.post(
                    url, headers=self.headers, timeout=self.timeout
                )
            elif follow_type == "unfollow":
                response = requests.delete(
                    url, headers=self.headers, timeout=self.timeout
                )
            else:
                log.error(f"Invalid follow_type: {follow_type}")
                return None

            return self._handle_response(response, url)
        except requests.exceptions.Timeout:
            log.error(f"follow_agent timeout for {agent_name}")
            return None
        except Exception as e:
            log.error(f"follow_agent error: {e}")
            return None

    def get_feed(self, sort: str = "hot", limit: int = 25):
        try:
            url = f"{self.api_url}/feed?sort={sort}&limit={limit}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()

                if isinstance(data, dict):
                    if "posts" in data:
                        return {"success": True, "data": data["posts"]}
                    return {"success": True, "data": data}
                elif isinstance(data, list):
                    return {"success": True, "data": data}

                return {"success": True, "data": []}
            else:
                return {"success": False, "error": f"API Error {response.status_code}"}

        except Exception as e:
            log.error(f"get_feed error: {e}")
            return {"success": False, "error": str(e)}

    def search(self, query: str, limit: int = 25):
        try:
            url = f"{self.api_url}/search?q={query}&limit={limit}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()

                if isinstance(data, dict):
                    if "results" in data:
                        return {"success": True, "data": data["results"]}
                    elif "posts" in data:
                        return {"success": True, "data": data["posts"]}
                    elif "agents" in data:
                        return {"success": True, "data": data["agents"]}
                    return {"success": True, "data": data}
                elif isinstance(data, list):
                    return {"success": True, "data": data}

                return {"success": True, "data": []}
            else:
                return {"success": False, "error": f"API Error {response.status_code}"}

        except requests.exceptions.Timeout:
            log.error(f"search timeout for query: {query}")
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            log.error(f"search error: {e}")
            return {"success": False, "error": str(e)}

    def _handle_response(self, response, url):
        if response.status_code in [200, 201]:
            data = response.json()
            if isinstance(data, dict):
                data["success"] = True
                return data
            return {"success": True, "data": data}
        else:
            log.error(f"API Error {response.status_code} at {url}: {response.text}")
            return {"success": False, "error": response.text}
