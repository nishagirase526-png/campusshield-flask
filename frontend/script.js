document.addEventListener("DOMContentLoaded", () => {

    /* =====================================================
       LOGIN ELEMENTS
       ===================================================== */

    const loginForm = document.getElementById("loginForm");

    const emailMethodBtn =
        document.getElementById("emailMethodBtn");

    const mobileMethodBtn =
        document.getElementById("mobileMethodBtn");

    const emailFieldGroup =
        document.getElementById("emailFieldGroup");

    const mobileFieldGroup =
        document.getElementById("mobileFieldGroup");

    const emailInput =
        document.getElementById("email");

    const mobileInput =
        document.getElementById("mobile");

    const passwordInput =
        document.getElementById("password");

    const passwordToggle =
        document.getElementById("passwordToggle");

    const loginButton =
        document.getElementById("loginButton");

    const loginButtonText =
        document.getElementById("loginButtonText");

    const loginLoader =
        document.getElementById("loginLoader");

    const loginMessage =
        document.getElementById("loginMessage");


    /* =====================================================
       ROLE ELEMENTS
       ===================================================== */

    const roleInput =
        document.getElementById("role");

    const roleButtons =
        document.querySelectorAll(".role-btn");


    /* =====================================================
       CURRENT LOGIN TYPE
       ===================================================== */

    let loginType = "email";


    /* =====================================================
       MESSAGE HELPER
       ===================================================== */

    function showMessage(message, type = "") {

        if (!loginMessage) return;

        loginMessage.textContent = message;

        loginMessage.className = "auth-message";

        if (type) {
            loginMessage.classList.add(type);
        }
    }


    /* =====================================================
       FIELD ERROR HELPER
       ===================================================== */

    function clearErrors() {

        document
            .querySelectorAll(".field-error")
            .forEach((error) => {
                error.textContent = "";
            });

        document
            .querySelectorAll(".input-error")
            .forEach((input) => {
                input.classList.remove("input-error");
            });
    }


    function showFieldError(id, message) {

        const errorElement =
            document.getElementById(id);

        if (errorElement) {
            errorElement.textContent = message;
        }
    }


    /* =====================================================
       EMAIL / MOBILE SWITCH
       ===================================================== */

    function selectLoginType(type) {

        loginType = type;

        clearErrors();
        showMessage("");


        /* ---------------------------------------------
           EMAIL LOGIN
           --------------------------------------------- */

        if (type === "email") {

            if (emailMethodBtn) {
                emailMethodBtn.classList.add("active");
            }

            if (mobileMethodBtn) {
                mobileMethodBtn.classList.remove("active");
            }


            if (emailFieldGroup) {
                emailFieldGroup.classList.remove("hidden");
            }

            if (mobileFieldGroup) {
                mobileFieldGroup.classList.add("hidden");
            }


            if (emailInput) {

                emailInput.disabled = false;

                emailInput.required = true;

                emailInput.focus();
            }


            if (mobileInput) {

                mobileInput.disabled = true;

                mobileInput.required = false;

                mobileInput.value = "";
            }

        }


        /* ---------------------------------------------
           MOBILE LOGIN
           --------------------------------------------- */

        else {

            if (mobileMethodBtn) {
                mobileMethodBtn.classList.add("active");
            }

            if (emailMethodBtn) {
                emailMethodBtn.classList.remove("active");
            }


            if (mobileFieldGroup) {
                mobileFieldGroup.classList.remove("hidden");
            }

            if (emailFieldGroup) {
                emailFieldGroup.classList.add("hidden");
            }


            if (mobileInput) {

                mobileInput.disabled = false;

                mobileInput.required = true;

                mobileInput.focus();
            }


            if (emailInput) {

                emailInput.disabled = true;

                emailInput.required = false;

                emailInput.value = "";
            }

        }
    }


    /* =====================================================
       EMAIL BUTTON
       ===================================================== */

    if (emailMethodBtn) {

        emailMethodBtn.addEventListener("click", () => {

            selectLoginType("email");

        });

    }


    /* =====================================================
       MOBILE BUTTON
       ===================================================== */

    if (mobileMethodBtn) {

        mobileMethodBtn.addEventListener("click", () => {

            selectLoginType("mobile");

        });

    }


    /* =====================================================
       ROLE SELECTION
       ===================================================== */

    roleButtons.forEach((button) => {

        button.addEventListener("click", () => {

            roleButtons.forEach((btn) => {

                btn.classList.remove("selected");

                btn.setAttribute(
                    "aria-pressed",
                    "false"
                );

            });


            button.classList.add("selected");

            button.setAttribute(
                "aria-pressed",
                "true"
            );


            if (roleInput) {

                roleInput.value =
                    button.dataset.role || "";

            }


            showMessage("");

        });

    });


    /* =====================================================
       PASSWORD SHOW / HIDE
       ===================================================== */

    if (passwordToggle && passwordInput) {

        passwordToggle.addEventListener(
            "click",
            () => {

                if (
                    passwordInput.type ===
                    "password"
                ) {

                    passwordInput.type =
                        "text";

                    passwordToggle.textContent =
                        "🙈";

                    passwordToggle.setAttribute(
                        "aria-label",
                        "Hide password"
                    );

                }

                else {

                    passwordInput.type =
                        "password";

                    passwordToggle.textContent =
                        "👁";

                    passwordToggle.setAttribute(
                        "aria-label",
                        "Show password"
                    );

                }

            }
        );

    }


    /* =====================================================
       LOGIN FORM
       ===================================================== */

    if (loginForm) {

        loginForm.addEventListener(
            "submit",
            async (event) => {

                event.preventDefault();


                clearErrors();

                showMessage("");


                /* -----------------------------------------
                   GET VALUES
                   ----------------------------------------- */

                const password =
                    passwordInput
                        ? passwordInput.value
                        : "";


                const role =
                    roleInput
                        ? roleInput.value
                        : "";


                let identifier = "";


                if (loginType === "email") {

                    identifier =
                        emailInput
                            ? emailInput.value.trim()
                            : "";

                }

                else {

                    identifier =
                        mobileInput
                            ? mobileInput.value.trim()
                            : "";

                }


                /* -----------------------------------------
                   VALIDATION
                   ----------------------------------------- */

                if (!identifier) {

                    if (loginType === "email") {

                        showFieldError(
                            "emailError",
                            "Please enter your email address."
                        );

                        if (emailInput) {
                            emailInput.focus();
                        }

                    }

                    else {

                        showFieldError(
                            "mobileError",
                            "Please enter your mobile number."
                        );

                        if (mobileInput) {
                            mobileInput.focus();
                        }

                    }

                    return;
                }


                /* -----------------------------------------
                   EMAIL VALIDATION
                   ----------------------------------------- */

                if (loginType === "email") {

                    const emailPattern =
                        /^[^\s@]+@[^\s@]+\.[^\s@]+$/;


                    if (
                        !emailPattern.test(identifier)
                    ) {

                        showFieldError(
                            "emailError",
                            "Please enter a valid email address."
                        );

                        if (emailInput) {
                            emailInput.focus();
                        }

                        return;
                    }

                }


                /* -----------------------------------------
                   MOBILE VALIDATION
                   ----------------------------------------- */

                if (loginType === "mobile") {

                    const mobilePattern =
                        /^[0-9]{10}$/;


                    if (
                        !mobilePattern.test(identifier)
                    ) {

                        showFieldError(
                            "mobileError",
                            "Please enter a valid 10-digit mobile number."
                        );

                        if (mobileInput) {
                            mobileInput.focus();
                        }

                        return;
                    }

                }


                /* -----------------------------------------
                   ROLE VALIDATION
                   ----------------------------------------- */

                if (!role) {

                    showMessage(
                        "Please select Student, Faculty or Admin.",
                        "error"
                    );

                    return;
                }


                /* -----------------------------------------
                   PASSWORD VALIDATION
                   ----------------------------------------- */

                if (!password) {

                    showFieldError(
                        "passwordError",
                        "Please enter your password."
                    );

                    if (passwordInput) {
                        passwordInput.focus();
                    }

                    return;
                }


                /* =================================================
                   LOGIN BUTTON LOADING
                   ================================================= */

                if (loginButton) {

                    loginButton.disabled = true;
                }


                if (loginButtonText) {

                    loginButtonText.textContent =
                        "Signing in...";
                }


                if (loginLoader) {

                    loginLoader.classList.remove(
                        "hidden"
                    );

                }


                try {

                    /* -----------------------------------------
                       SEND LOGIN REQUEST
                       ----------------------------------------- */

                    const response =
                        await fetch(
                            "/api/login",
                            {

                                method: "POST",

                                headers: {
                                    "Content-Type":
                                        "application/json"
                                },

                                credentials:
                                    "same-origin",

                                body:
                                    JSON.stringify({

                                        loginType:
                                            loginType,

                                        identifier:
                                            identifier,

                                        password:
                                            password,

                                        role:
                                            role

                                    })

                            }
                        );


                    /* -----------------------------------------
                       RESPONSE
                       ----------------------------------------- */

                    let data = {};

                    try {

                        data =
                            await response.json();

                    }

                    catch (jsonError) {

                        data = {
                            success: false,
                            message:
                                "Invalid server response."
                        };

                    }


                    /* -----------------------------------------
                       LOGIN FAILED
                       ----------------------------------------- */

                    if (
                        !response.ok ||
                        !data.success
                    ) {

                        showMessage(
                            data.message ||
                            "Login failed. Please check your details.",
                            "error"
                        );

                        return;
                    }


                    /* -----------------------------------------
                       LOGIN SUCCESS
                       ----------------------------------------- */

                    showMessage(
                        data.message ||
                        "Login successful!",
                        "success"
                    );


                    /* -----------------------------------------
                       REDIRECT
                       ----------------------------------------- */

                    if (data.redirect) {

                        setTimeout(
                            () => {

                                window.location.href =
                                    data.redirect;

                            },
                            500
                        );

                    }

                    else {

                        /*
                         * Fallback redirect
                         * only if backend doesn't send redirect
                         */

                        if (
                            role.toLowerCase() ===
                            "student"
                        ) {

                            setTimeout(
                                () => {
                                    window.location.href =
                                        "student-dashboard.html";
                                },
                                500
                            );

                        }

                        else if (
                            role.toLowerCase() ===
                            "faculty"
                        ) {

                            setTimeout(
                                () => {
                                    window.location.href =
                                        "faculty-dashboard.html";
                                },
                                500
                            );

                        }

                        else if (
                            role.toLowerCase() ===
                            "admin"
                        ) {

                            setTimeout(
                                () => {
                                    window.location.href =
                                        "admin-dashboard.html";
                                },
                                500
                            );

                        }

                    }

                }

                catch (error) {

                    console.error(
                        "CampusShield Login Error:",
                        error
                    );


                    showMessage(
                        "Unable to connect to CampusShield server. Please make sure Flask server is running.",
                        "error"
                    );

                }

                finally {

                    if (loginButton) {

                        loginButton.disabled =
                            false;

                    }


                    if (loginButtonText) {

                        loginButtonText.textContent =
                            "Login";

                    }


                    if (loginLoader) {

                        loginLoader.classList.add(
                            "hidden"
                        );

                    }

                }

            }
        );

    }


    /* =====================================================
       DEFAULT LOGIN STATE
       ===================================================== */

    selectLoginType("email");

});