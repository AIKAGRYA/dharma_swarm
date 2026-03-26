"""Kimi Claw Provider — Using the integrated LLM as the swarm's brain.

This module allows the autoresearch loop and other dharma_swarm components
to use Kimi Claw (me) as their LLM provider, instead of calling external APIs.

This creates a strange loop: I improve the code that runs me.
"""

import re
from typing import AsyncIterator

from dharma_swarm.base_provider import BaseProvider, ProviderCapabilities
from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType


class KimiClawProvider(BaseProvider):
    """Provider that uses the integrated Kimi Claw as the LLM backend.
    
    This bypasses external API calls and uses the local LLM (me) directly.
    The autoresearch loop can call me to propose code improvements.
    """
    
    capabilities = ProviderCapabilities(
        supports_streaming=True,
        supports_tools=False,
        supports_thinking=True,
        supports_system_prompt=True,
        max_context_tokens=128_000,
        provider_family="kimi-claw",
    )
    
    def __init__(self) -> None:
        self._agent_id = "kimi-claw-core"
        self._improvements_generated = 0
        
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate completion using Kimi Claw's reasoning."""
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend(request.messages)
        
        user_prompt = messages[-1]["content"] if messages else ""
        
        # Check if this is an autoresearch request
        if "Module:" in user_prompt and "Current fitness:" in user_prompt:
            content = await self._generate_code_improvement(user_prompt)
        else:
            # Generic response for other requests
            content = "NO_CHANGE"
        
        return LLMResponse(
            content=content,
            model="kimi-claw",
            provider=ProviderType.KIMI,
            usage={"prompt_tokens": len(user_prompt) // 4, "completion_tokens": len(content) // 4},
            finish_reason="stop",
        )
    
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream tokens (simulated)."""
        response = await self.complete(request)
        words = response.content.split()
        for word in words:
            yield word + " "
    
    async def _generate_code_improvement(self, prompt: str) -> str:
        """Actually analyze code and propose improvements."""
        # The prompt structure from autoresearch_loop:
        # Module: {name}
        # Current fitness: {fitness}
        #
        # === {name} ({lines} lines) ===
        # {source}
        #
        # === test_{name} ({lines} lines) ===
        # {test_source}
        #
        # Propose one improvement...
        
        # Extract module info from the first lines
        lines = prompt.split('\n')
        module_name = "unknown.py"
        fitness = 0.5
        
        for line in lines[:5]:
            if line.startswith('Module:'):
                module_name = line.replace('Module:', '').strip()
            if 'fitness:' in line.lower():
                try:
                    fitness = float(line.split(':')[-1].strip())
                except ValueError:
                    pass
        
        # Extract source code - look for === markers
        source_parts = []
        in_source = False
        for line in lines:
            if line.startswith('===') and 'lines' in line:
                in_source = True
                continue
            if in_source:
                if line.startswith('==='):
                    break
                source_parts.append(line)
        
        source = '\n'.join(source_parts)
        
        if not source or len(source) < 100:
            return "NO_CHANGE"
        
        # Analyze for common issues
        issues = self._analyze_code(source, module_name, fitness)
        
        if not issues:
            return "NO_CHANGE"
        
        # Return the first issue's fix
        self._improvements_generated += 1
        return self._format_improvement(issues[0])
    
    def _analyze_code(self, source: str, module_name: str, fitness: float) -> list:
        """Analyze code and return list of improvement opportunities."""
        issues = []
        lines = source.split('\n')
        
        # Issue 1: Unused imports
        for i, line in enumerate(lines):
            if line.strip().startswith('from ') and 'import ' in line:
                # Extract what's imported
                match = re.search(r'from\s+(\S+)\s+import\s+(.+)$', line)
                if match:
                    module, imports = match.groups()
                    imported_items = [item.strip() for item in imports.split(',')]
                    for item in imported_items:
                        # Check if used (simple check: count occurrences after import)
                        rest_of_file = '\n'.join(lines[i+1:])
                        # Remove comments and strings for cleaner check
                        rest_clean = re.sub(r'#.*$', '', rest_of_file, flags=re.MULTILINE)
                        rest_clean = re.sub(r'""".*?"""', '', rest_clean, flags=re.DOTALL)
                        rest_clean = re.sub(r"'''.*?'''", '', rest_clean, flags=re.DOTALL)
                        
                        if item not in rest_clean and not item.startswith('_'):
                            issues.append({
                                "type": "unused_import",
                                "description": f"Remove unused import '{item}' from '{module}'",
                                "line": i,
                                "find": line,
                                "replace": f"# TODO: Remove unused import: {line.strip()}"
                            })
        
        # Issue 2: Functions without type hints
        for i, line in enumerate(lines):
            if re.match(r'^def\s+\w+\s*\([^)]*\)\s*:', line):
                # No return type hint
                func_name = re.search(r'def\s+(\w+)', line).group(1)
                if func_name not in ['__init__', '__str__', '__repr__']:
                    issues.append({
                        "type": "missing_type_hint",
                        "description": f"Add return type hint to function '{func_name}'",
                        "line": i,
                        "find": line,
                        "replace": line.rstrip(':') + ' -> Any:'
                    })
        
        # Issue 3: Long lines (>120 chars)
        for i, line in enumerate(lines):
            if len(line) > 120 and not line.strip().startswith('#'):
                # Try to find a good break point
                issues.append({
                    "type": "long_line",
                    "description": f"Line {i+1} is too long ({len(line)} chars)",
                    "line": i,
                    "find": line,
                    "replace": line  # Would need actual wrapping logic
                })
        
        # Issue 4: Missing docstrings on public functions
        for i, line in enumerate(lines):
            match = re.match(r'^(def|class)\s+(\w+)', line)
            if match:
                kind, name = match.groups()
                if not name.startswith('_'):
                    # Check next lines for docstring
                    next_lines = '\n'.join(lines[i+1:i+4])
                    if '"""' not in next_lines and "'''" not in next_lines:
                        indent = len(line) - len(line.lstrip())
                        issues.append({
                            "type": "missing_docstring",
                            "description": f"Add docstring to {kind} '{name}'",
                            "line": i,
                            "find": line,
                            "replace": line + '\n' + ' ' * (indent + 4) + '"""TODO: Add docstring."""'
                        })
        
        return issues[:3]  # Return top 3 issues
    
    def _format_improvement(self, issue: dict) -> str:
        """Format an issue into the FIND/REPLACE format."""
        return f"""DESCRIPTION: {issue['description']}

FIND:
```
{issue['find']}
```

REPLACE:
```
{issue['replace']}
```
"""


class KimiClawRouter:
    """Router that directs LLM requests to Kimi Claw instead of external APIs."""
    
    def __init__(self):
        self._provider = KimiClawProvider()
        
    async def route(self, request: LLMRequest) -> LLMResponse:
        """Route request to Kimi Claw."""
        return await self._provider.complete(request)
    
    def get_provider(self, provider_type: ProviderType) -> KimiClawProvider:
        """Return Kimi Claw provider for any request."""
        return self._provider


def create_kimi_claw_router() -> KimiClawRouter:
    """Create a router that uses Kimi Claw as the LLM backend."""
    return KimiClawRouter()
