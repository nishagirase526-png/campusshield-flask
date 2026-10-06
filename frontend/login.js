document.addEventListener("DOMContentLoaded", function () {

    const loginForm = document.getElementById("loginForm");
    const loginType = document.getElementById("loginType");
    const role = document.getElementById("role");
    const identifier = document.getElementById("identifier");
    const identifierLabel = document.getElementById("identifierLabel");
    const password = document.getElementById("password");
    const passwordToggle = document.getElementById("passwordToggle");
    const loginButton = document.getElementById("loginButton");
    const loginMessage = document.getElementById("loginMessage");
    const methodButtons = document.querySelectorAll(".register-method-btn");
    const roleButtons = document.querySelectorAll(".login-role-btn");

    methodButtons.forEach(function (button) {

        button.addEventListener("click", function () {

            const method = button.dataset.method;

            loginType.value = method;

            methodButtons.forEach(function (btn) {
                btn.classList.remove("active");
            });

            button.classList.add("active");

            if (method === "mobile") {

                identifier.type = "tel";
                identifier.placeholder = "Enter your mobile number";
                identifierLabel.textContent = "Mobile number";

            } else {

                identifier.type = "email";
                identifier.placeholder = "Enter your email address";
                identifierLabel.textContent = "Email address";

            }

            identifier.value = "";
            identifier.focus();

        });

    });

    roleButtons.forEach(function (button) {

        button.addEventListener("click", function () {

            role.value = button.dataset.role;

            roleButtons.forEach(function (btn) {
                btn.classList.remove("active");
            });

            button.classList.add("active");

        });

    });

    passwordToggle.addEventListener("click", function () {

        if (password.type === "password") {

            password.type = "text";
            passwordToggle.textContent = "Hide";
            passwordToggle.setAttribute("aria-label", "Hide password");
            passwordToggle.setAttribute("aria-pressed", "true");

        } else {

            password.type = "password";
            passwordToggle.textContent = "Show";
            passwordToggle.setAttribute("aria-label", "Show password");
            passwordToggle.setAttribute("aria-pressed", "false");

        }

    });

    function showMessage(message, type) {

        loginMessage.textContent = message;
        loginMessage.className = "campus-login-message " + (type || "error");

    }

    loginForm.addEventListener("submit", async function (event) {

        event.preventDefault();

        showMessage("", "");

        const selectedLoginType = loginType.value;
        const selectedRole = (role.value || "").trim().toLowerCase();
        const enteredIdentifier = identifier.value.trim();
        const enteredPassword = password.value;

        if (
            selectedRole !== "student"
            && selectedRole !== "faculty"
            && selectedRole !== "admin"
        ) {

            showMessage("Please select Student, Faculty, or Admin.");
            return;

        }

        if (!enteredIdentifier) {

            showMessage(
                selectedLoginType === "email"
                    ? "Please enter your email address."
                    : "Please enter your mobile number."
            );

            identifier.focus();
            return;

        }

        if (selectedLoginType === "email") {

            const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

            if (!emailPattern.test(enteredIdentifier)) {

                showMessage("Please enter a valid email address.");
                identifier.focus();
                return;

            }

        } else {

            const mobilePattern = /^\+?[0-9]{10,15}$/;
            const cleanMobile = enteredIdentifier.replace(/[\s\-()]/g, "");

            if (!mobilePattern.test(cleanMobile)) {

                showMessage("Please enter a valid mobile number.");
                identifier.focus();
                return;

            }

        }

        if (!enteredPassword) {

            showMessage("Please enter your password.");
            password.focus();
            return;

        }

        loginButton.disabled = true;
        loginButton.innerHTML = "Signing in...";

        try {

            const response = await fetch("/api/login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                credentials: "include",
                body: JSON.stringify({
                    loginType: selectedLoginType,
                    identifier: enteredIdentifier,
                    password: enteredPassword,
                    role: selectedRole
                })
            });

            const contentType = response.headers.get("content-type") || "";
            if (!contentType.includes("application/json")) {
                throw new Error(
                    "The login service returned an unexpected response. Please restart the CampusShield Flask server and try again."
                );
            }

            const data = await response.json();

            if (!response.ok || !data.success) {

                showMessage(
                    data.message ||
                    "Login failed. Please check your details."
                );

                loginButton.disabled = false;
                loginButton.innerHTML =
                    'Sign in <span aria-hidden="true">→</span>';

                return;

            }

            showMessage("Login successful! Redirecting...", "success");

            const dashboardByRole = {
                admin: "admin-dashboard.html",
                faculty: "faculty-dashboard.html",
                student: "student-dashboard.html"
            };
            const authenticatedRole = (data.role || "").trim().toLowerCase();
            if (
                authenticatedRole !== selectedRole
                || !dashboardByRole[authenticatedRole]
            ) {
                showMessage(
                    "The authenticated role did not match the selected role. Please sign in again."
                );
                loginButton.disabled = false;
                loginButton.innerHTML =
                    'Sign in <span aria-hidden="true">→</span>';
                return;
            }

            setTimeout(function () {

                window.location.href = "/" + dashboardByRole[authenticatedRole];

            }, 500);

        } catch (error) {

            console.error("Login Error:", error);

            showMessage(
                "Unable to connect to server. Please make sure Flask is running."
            );

            loginButton.disabled = false;
            loginButton.innerHTML =
                'Sign in <span aria-hidden="true">→</span>';

        }

    });

});
