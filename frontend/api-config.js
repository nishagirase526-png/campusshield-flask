// Keep local Flask development same-origin. Hosted frontends send API calls to
// the separately deployed CampusShield backend.
(function () {
    const backendBaseUrl = "https://campusshield-5t1p.onrender.com";
    const isLocalDevelopment = ["localhost", "127.0.0.1", "::1"].includes(
        window.location.hostname
    );
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
