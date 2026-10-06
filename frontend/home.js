/**
 * CampusShield - Clean ERP Landing Page Script
 * Lightweight interactivity for navigation, smooth scrolling, and mobile drawer.
 */

document.addEventListener("DOMContentLoaded", function () {
    // 1. Header scroll shadow enhancement
    const header = document.querySelector(".cs-header");
    function handleScroll() {
        if (!header) return;
        if (window.scrollY > 15) {
            header.classList.add("scrolled");
        } else {
            header.classList.remove("scrolled");
        }
    }
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();

    // 2. Mobile Menu Drawer Toggle
    const navToggle = document.getElementById("csNavToggle");
    const mobileMenu = document.getElementById("csMobileMenu");

    if (navToggle && mobileMenu) {
        navToggle.addEventListener("click", function () {
            const isExpanded = navToggle.getAttribute("aria-expanded") === "true";
            navToggle.setAttribute("aria-expanded", String(!isExpanded));
            mobileMenu.classList.toggle("active");

            const icon = navToggle.querySelector("span");
            if (icon) {
                icon.textContent = isExpanded ? "☰" : "✕";
            }
        });

        // Close mobile menu when clicking any menu link
        const mobileLinks = mobileMenu.querySelectorAll("a");
        mobileLinks.forEach(function (link) {
            link.addEventListener("click", function () {
                mobileMenu.classList.remove("active");
                navToggle.setAttribute("aria-expanded", "false");
                const icon = navToggle.querySelector("span");
                if (icon) icon.textContent = "☰";
            });
        });

        // Close on escape key
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && mobileMenu.classList.contains("active")) {
                mobileMenu.classList.remove("active");
                navToggle.setAttribute("aria-expanded", "false");
                const icon = navToggle.querySelector("span");
                if (icon) icon.textContent = "☰";
                navToggle.focus();
            }
        });
    }

    // 3. Smooth scrolling for anchor links (e.g. #about)
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
        anchor.addEventListener("click", function (e) {
            const targetId = this.getAttribute("href");
            if (!targetId || targetId === "#") return;
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                e.preventDefault();
                const headerOffset = 80;
                const elementPosition = targetElement.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

                window.scrollTo({
                    top: offsetPosition,
                    behavior: "smooth"
                });
            }
        });
    });
});
