document.addEventListener("DOMContentLoaded", function () {

    const forgotForm = document.getElementById("forgotForm");
    const loginType = document.getElementById("loginType");
    const identifier = document.getElementById("identifier");
    const identifierLabel = document.getElementById("identifierLabel");
    const otp = document.getElementById("otp");
    const newPassword = document.getElementById("newPassword");
    const confirmPassword = document.getElementById("confirmPassword");
    const sendOtpButton = document.getElementById("sendOtpButton");
    const verifyOtpButton = document.getElementById("verifyOtpButton");
    const resetButton = document.getElementById("resetButton");
    const forgotMessage = document.getElementById("forgotMessage");
    const otpHint = document.getElementById("otpHint");
    const methodButtons = document.querySelectorAll(".register-method-btn");
    const stepIdentifier = document.getElementById("stepIdentifier");
    const stepOtp = document.getElementById("stepOtp");
    const stepPassword = document.getElementById("stepPassword");
    const passwordToggle = document.getElementById("passwordToggle");
    const confirmPasswordToggle = document.getElementById("confirmPasswordToggle");

    let resetToken = "";

    function showStep(step) {

        stepIdentifier.classList.remove("active");
        stepOtp.classList.remove("active");
        stepPassword.classList.remove("active");
        step.classList.add("active");

    }

    function showMessage(message, type) {

        forgotMessage.textContent = message;
        forgotMessage.className = "campus-login-message " + (type || "error");

    }

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

    function setupPasswordToggle(button, input) {

        button.addEventListener("click", function () {

            if (input.type === "password") {

                input.type = "text";
                button.textContent = "Hide";

            } else {

                input.type = "password";
                button.textContent = "Show";

            }

        });

    }

    setupPasswordToggle(passwordToggle, newPassword);
    setupPasswordToggle(confirmPasswordToggle, confirmPassword);

    sendOtpButton.addEventListener("click", async function () {

        showMessage("", "");

        const method = loginType.value;
        const value = identifier.value.trim();

        if (!value) {

            showMessage(
                method === "email"
                    ? "Please enter your email address."
                    : "Please enter your mobile number."
            );

            return;

        }

        sendOtpButton.disabled = true;
        sendOtpButton.textContent = "Sending OTP...";

        try {

            const response = await fetch("/api/auth/forgot-password", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    loginType: method,
                    identifier: value
                })
            });

            const data = await response.json();

            if (!response.ok || !data.success) {

                showMessage(
                    data.message || "Unable to send OTP."
                );

                return;

            }

            let hint = "Enter the 6-digit OTP sent to " + value + ".";

            if (data.developmentHint) {

                hint += " " + data.developmentHint;

            }

            otpHint.textContent = hint;
            showMessage(data.message, "success");
            showStep(stepOtp);
            otp.focus();

        } catch (error) {

            console.error("Forgot Password Error:", error);
            showMessage("Unable to connect to the server.");

        } finally {

            sendOtpButton.disabled = false;
            sendOtpButton.textContent = "Send OTP";

        }

    });

    verifyOtpButton.addEventListener("click", async function () {

        showMessage("", "");

        const enteredOtp = otp.value.trim();

        if (!/^[0-9]{6}$/.test(enteredOtp)) {

            showMessage("Please enter a valid 6-digit OTP.");
            return;

        }

        verifyOtpButton.disabled = true;
        verifyOtpButton.textContent = "Verifying...";

        try {

            const response = await fetch("/api/auth/verify-otp", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    loginType: loginType.value,
                    identifier: identifier.value.trim(),
                    otp: enteredOtp
                })
            });

            const data = await response.json();

            if (!response.ok || !data.success) {

                showMessage(
                    data.message || "Invalid OTP."
                );

                return;

            }

            resetToken = data.resetToken || "";
            showMessage("OTP verified. Set a new password.", "success");
            showStep(stepPassword);
            newPassword.focus();

        } catch (error) {

            console.error("Verify OTP Error:", error);
            showMessage("Unable to connect to the server.");

        } finally {

            verifyOtpButton.disabled = false;
            verifyOtpButton.textContent = "Verify OTP";

        }

    });

    forgotForm.addEventListener("submit", async function (event) {

        event.preventDefault();

        showMessage("", "");

        if (!resetToken) {

            showMessage("Please verify the OTP first.");
            return;

        }

        if (newPassword.value.length < 8) {

            showMessage("Password must contain at least 8 characters.");
            return;

        }

        if (newPassword.value !== confirmPassword.value) {

            showMessage("Passwords do not match.");
            return;

        }

        resetButton.disabled = true;
        resetButton.textContent = "Saving...";

        try {

            const response = await fetch("/api/auth/reset-password", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    resetToken: resetToken,
                    newPassword: newPassword.value,
                    confirmPassword: confirmPassword.value
                })
            });

            const data = await response.json();

            if (!response.ok || !data.success) {

                showMessage(
                    data.message || "Unable to reset password."
                );

                return;

            }

            showMessage(
                "Password reset successfully! Redirecting to login...",
                "success"
            );

            setTimeout(function () {

                window.location.href = "/login.html";

            }, 1200);

        } catch (error) {

            console.error("Reset Password Error:", error);
            showMessage("Unable to connect to the server.");

        } finally {

            resetButton.disabled = false;
            resetButton.textContent = "Reset password";

        }

    });

});
