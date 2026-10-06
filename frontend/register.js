document.addEventListener("DOMContentLoaded", function () {

    const registerForm = document.getElementById("registerForm");
    const fullName = document.getElementById("fullName");
    const registerMethod = document.getElementById("registerMethod");
    const identifier = document.getElementById("identifier");
    const identifierLabel = document.getElementById("identifierLabel");
    const otp = document.getElementById("otp");
    const password = document.getElementById("password");
    const confirmPassword = document.getElementById("confirmPassword");
    const passwordToggle = document.getElementById("passwordToggle");
    const confirmPasswordToggle = document.getElementById("confirmPasswordToggle");
    const sendOtpButton = document.getElementById("sendOtpButton");
    const verifyOtpButton = document.getElementById("verifyOtpButton");
    const registerButton = document.getElementById("registerButton");
    const registerMessage = document.getElementById("registerMessage");
    const otpHint = document.getElementById("otpHint");
    const methodButtons = document.querySelectorAll(".register-method-btn");
    const stepDetails = document.getElementById("stepDetails");
    const stepOtp = document.getElementById("stepOtp");
    const stepPassword = document.getElementById("stepPassword");
    const collegeId = document.getElementById("collegeId");
    const studentClassId = document.getElementById("studentClassId");
    const rollNumber = document.getElementById("rollNumber");

    let otpVerified = false;
    let verificationToken = "";
    let classRequestId = 0;

    function showStep(step) {

        stepDetails.classList.remove("active");
        stepOtp.classList.remove("active");
        stepPassword.classList.remove("active");
        step.classList.add("active");

    }

    function showMessage(message, isError) {

        registerMessage.textContent = message;
        registerMessage.style.color = isError === false ? "#16a34a" : "#dc2626";

    }

    function validIdentifier(method, value) {

        if (method === "email") {

            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

        }

        return /^\+?[0-9]{10,15}$/.test(value.replace(/[\s\-()]/g, ""));

    }

    methodButtons.forEach(function (button) {

        button.addEventListener("click", function () {

            const method = button.dataset.method;

            registerMethod.value = method;

            methodButtons.forEach(function (btn) {
                btn.classList.remove("active");
            });

            button.classList.add("active");

            if (method === "email") {

                identifierLabel.textContent = "Email address";
                identifier.type = "email";
                identifier.placeholder = "Enter your email address";
                identifier.autocomplete = "email";

            } else {

                identifierLabel.textContent = "Mobile number";
                identifier.type = "tel";
                identifier.placeholder = "Enter your mobile number";
                identifier.autocomplete = "tel";

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

    setupPasswordToggle(passwordToggle, password);
    setupPasswordToggle(confirmPasswordToggle, confirmPassword);

    async function loadColleges() {

        if (!collegeId) {
            return;
        }

        try {

            const response = await fetch("/api/colleges");

            if (!response.ok) {

                showMessage("Unable to load colleges. Please refresh the page.");
                return;

            }

            const colleges = await response.json();

            if (!Array.isArray(colleges) || colleges.length === 0) {

                showMessage("No colleges are available for registration.");
                return;

            }

            colleges.forEach(function (college) {

                const option = document.createElement("option");
                option.value = String(college.id);
                option.textContent = college.name;
                collegeId.appendChild(option);

            });

        } catch (error) {

            showMessage("Unable to load colleges. Please refresh the page.");

        }

    }

    loadColleges();

    async function loadClasses() {
        const requestId = ++classRequestId;
        studentClassId.disabled = true;
        studentClassId.innerHTML = "<option value=''>Loading classes...</option>";

        if (!collegeId.value) {
            studentClassId.innerHTML = "<option value=''>Select your college first</option>";
            return;
        }

        try {
            const query = new URLSearchParams({ college_id: collegeId.value });
            const response = await fetch("/api/classes?" + query.toString());
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.message || "Unable to load classes.");
            }
            if (requestId !== classRequestId) return;

            studentClassId.replaceChildren();
            const classes = data.classes || [];
            if (!classes.length) {
                const option = document.createElement("option");
                option.value = "";
                option.textContent = "No classes available";
                studentClassId.appendChild(option);
                showMessage("No classes are available for this college yet.");
                return;
            }

            const placeholder = document.createElement("option");
            placeholder.value = "";
            placeholder.textContent = "Select your class";
            studentClassId.appendChild(placeholder);
            classes.forEach(function (item) {
                const option = document.createElement("option");
                option.value = String(item.id);
                option.textContent = [
                    item.course,
                    "Year " + item.year_level,
                    "Semester " + item.semester,
                    item.division,
                    item.academic_year
                ].filter(Boolean).join(" · ");
                studentClassId.appendChild(option);
            });
            studentClassId.disabled = false;
        } catch (error) {
            if (requestId !== classRequestId) return;
            studentClassId.innerHTML = "<option value=''>Unable to load classes</option>";
            showMessage(error.message || "Unable to load classes.");
        }
    }

    collegeId.addEventListener("change", loadClasses);

    sendOtpButton.addEventListener("click", async function () {

        showMessage("");

        const name = fullName.value.trim();
        const method = registerMethod.value;
        const value = identifier.value.trim();

        if (!name) {

            showMessage("Please enter your full name.");
            fullName.focus();
            return;

        }

        if (!value) {

            showMessage(
                method === "email"
                    ? "Please enter your email address."
                    : "Please enter your mobile number."
            );

            identifier.focus();
            return;

        }

        if (!validIdentifier(method, value)) {

            showMessage(
                method === "email"
                    ? "Please enter a valid email address."
                    : "Please enter a valid mobile number."
            );

            identifier.focus();
            return;

        }

        if (!collegeId.value) {

            showMessage("Please select your college.");
            collegeId.focus();
            return;

        }

        if (!studentClassId.value || !rollNumber.value.trim()) {
            showMessage("Please select your class and enter your roll number.");
            studentClassId.focus();
            return;
        }

        sendOtpButton.disabled = true;
        sendOtpButton.textContent = "Sending OTP...";

        try {

            const response = await fetch("/api/register/send-otp", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    name: name,
                    registerMethod: method,
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

            showMessage(data.message, false);
            showStep(stepOtp);
            otp.focus();

        } catch (error) {

            console.error("Register OTP Error:", error);
            showMessage("Unable to connect to the server.");

        } finally {

            sendOtpButton.disabled = false;
            sendOtpButton.innerHTML = 'Send OTP <span>→</span>';

        }

    });

    verifyOtpButton.addEventListener("click", async function () {

        showMessage("");

        const enteredOtp = otp.value.trim();

        if (!/^[0-9]{6}$/.test(enteredOtp)) {

            showMessage("Please enter a valid 6-digit OTP.");
            otp.focus();
            return;

        }

        verifyOtpButton.disabled = true;
        verifyOtpButton.textContent = "Verifying...";

        try {

            const response = await fetch("/api/register/verify-otp", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    registerMethod: registerMethod.value,
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

            otpVerified = true;
            verificationToken = data.verificationToken || "";
            if (!verificationToken) {
                otpVerified = false;
                showMessage("OTP verification did not return a registration token.");
                return;
            }
            showMessage("OTP verified. Create your password.", false);
            showStep(stepPassword);
            password.focus();

        } catch (error) {

            console.error("Verify OTP Error:", error);
            showMessage("Unable to connect to the server.");

        } finally {

            verifyOtpButton.disabled = false;
            verifyOtpButton.textContent = "Verify OTP";

        }

    });

    registerForm.addEventListener("submit", async function (event) {

        event.preventDefault();

        showMessage("");

        if (!otpVerified) {

            showMessage("Please verify the OTP first.");
            return;

        }

        const pass = password.value;
        const confirm = confirmPassword.value;

        if (pass.length < 8) {

            showMessage("Password must contain at least 8 characters.");
            password.focus();
            return;

        }

        if (pass !== confirm) {

            showMessage("Passwords do not match.");
            confirmPassword.focus();
            return;

        }

        if (!collegeId.value) {

            showMessage("Please select your college.");
            collegeId.focus();
            return;

        }

        if (!studentClassId.value || !rollNumber.value.trim()) {
            showMessage("Please select your class and enter your roll number.");
            studentClassId.focus();
            return;
        }

        registerButton.disabled = true;
        registerButton.innerHTML = "Creating account...";

        try {

            const response = await fetch("/api/register", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    name: fullName.value.trim(),
                    registerMethod: registerMethod.value,
                    identifier: identifier.value.trim(),
                    verificationToken: verificationToken,
                    password: pass,
                    confirmPassword: confirm,
                    college_id: Number(collegeId.value),
                    class_id: Number(studentClassId.value),
                    roll_number: rollNumber.value.trim()
                })
            });

            const data = await response.json();

            if (!response.ok || !data.success) {

                showMessage(
                    data.message || "Unable to create account."
                );

                return;

            }

            showMessage(
                "Account created successfully! Redirecting to login...",
                false
            );

            setTimeout(function () {

                window.location.href = "/login.html";

            }, 1200);

        } catch (error) {

            console.error("Register Error:", error);
            showMessage("Unable to connect to the server.");

        } finally {

            registerButton.disabled = false;
            registerButton.innerHTML = 'Create account <span>→</span>';

        }

    });

});
