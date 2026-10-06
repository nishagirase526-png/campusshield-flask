// Keep local development and the single-service Railway deployment same-origin.
// The existing Render frontend continues to use its separately hosted backend.
(function () {
    const hostname = window.location.hostname.toLowerCase();
    const renderBackendBaseUrl = "https://campusshield-5t1p.onrender.com";
    // Railway serves the Flask app and frontend from one service, so API calls
    // should stay on that service's origin. Keep the existing Render frontend
    // pointed at its separately hosted backend.
    const backendBaseUrl = hostname.endsWith(".onrender.com")
        ? renderBackendBaseUrl
        : window.location.origin;
    const isLocalDevelopment = ["localhost", "127.0.0.1", "::1"].includes(
        hostname
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
