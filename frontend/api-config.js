// Keep local development and the single-service Railway deployment same-origin.
(function () {
    const hostname = window.location.hostname.toLowerCase();
    const isLocalDevelopment = ["localhost", "127.0.0.1", "::1"].includes(hostname);
    const backendBaseUrl = window.location.origin;
    const originalFetch = window.fetch.bind(window);

    window.fetch = function (input, init) {
        const requestUrl =
            typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        const isApiRequest = requestUrl.startsWith("/api/");

        if (!isApiRequest || isLocalDevelopment) {
            return originalFetch(input, init);
        }

        const apiUrl = `${backendBaseUrl}${requestUrl}`;
        const requestOptions = { ...(init || {}) };
        if (!requestOptions.credentials) {
            requestOptions.credentials = "include";
        }

        const apiInput = input instanceof Request
            ? new Request(apiUrl, input)
            : apiUrl;
        return originalFetch(apiInput, requestOptions);
    };
})();
