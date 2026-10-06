(async function addAdminManagementBanner() {
    try {
        const response = await fetch("/api/auth/me", {
            credentials: "same-origin",
            cache: "no-store"
        });
        if (!response.ok) return;

        const result = await response.json();
        const user = result.user || {};
        if (!user.admin_managed) return;

        const banner = document.createElement("aside");
        banner.setAttribute("role", "status");
        banner.style.cssText = [
            "position:sticky",
            "top:0",
            "z-index:10000",
            "display:flex",
            "align-items:center",
            "justify-content:space-between",
            "gap:16px",
            "padding:12px 20px",
            "background:#6b21a8",
            "color:#fff",
            "font:600 15px/1.4 Arial,sans-serif",
            "box-shadow:0 3px 12px rgba(30,15,45,.22)"
        ].join(";");

        const label = document.createElement("span");
        const roleName = user.role === "faculty" ? "Faculty" : "Student";
        label.textContent = `Admin access: managing ${roleName} account — ${user.name || "Selected user"}`;

        const stopButton = document.createElement("button");
        stopButton.type = "button";
        stopButton.textContent = "Return to Admin";
        stopButton.style.cssText = [
            "flex:0 0 auto",
            "border:1px solid rgba(255,255,255,.75)",
            "border-radius:7px",
            "padding:8px 12px",
            "background:#fff",
            "color:#5b1a91",
            "font:700 14px Arial,sans-serif",
            "cursor:pointer"
        ].join(";");
        stopButton.addEventListener("click", async function () {
            stopButton.disabled = true;
            stopButton.textContent = "Returning…";
            try {
                const stopped = await fetch("/api/admin/stop-managing", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { "Content-Type": "application/json" },
                    body: "{}"
                });
                const stoppedResult = await stopped.json();
                if (!stopped.ok || !stoppedResult.success) {
                    throw new Error(stoppedResult.message || "Unable to restore Admin access.");
                }
                window.location.assign("/admin-users.html");
            } catch (error) {
                stopButton.disabled = false;
                stopButton.textContent = "Return to Admin";
                window.alert(error.message || "Unable to restore Admin access.");
            }
        });

        banner.append(label, stopButton);
        document.body.prepend(banner);
    } catch (error) {
        console.error("Unable to load Admin management controls:", error);
    }
})();
