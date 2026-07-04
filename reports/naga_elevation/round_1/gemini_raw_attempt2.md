Attempt 1 failed with status 503. Retrying with backoff... _ApiError: {"error":{"code":503,"message":"This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.","status":"UNAVAILABLE"}}
    at throwErrorIfNotOK (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-ETUADTWF.js:36178:24)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-ETUADTWF.js:35929:7
    at async Models.generateContent (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-ETUADTWF.js:36988:16)
    at async file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:278074:26
    at async file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:255118:23
    at async retryWithBackoff (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:275074:23)
    at async BaseLlmClient._generateWithRetry (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:275331:14)
    at async BaseLlmClient.generateJson (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:275238:21)
    at async NumericalClassifierStrategy.route (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:321738:28) {
  status: 503
}
