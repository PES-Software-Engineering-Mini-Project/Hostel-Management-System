document.addEventListener("DOMContentLoaded", () => {
  const password = document.querySelector("#id_password");
  const toggle = document.querySelector("[data-password-toggle]");
  const form = document.querySelector("[data-login-form]");
  const submitButton = form?.querySelector("button[type='submit']");

  toggle?.addEventListener("click", () => {
    const showPassword = password.type === "password";
    password.type = showPassword ? "text" : "password";
    toggle.textContent = showPassword ? "Hide" : "Show";
    toggle.setAttribute("aria-label", showPassword ? "Hide password" : "Show password");
  });

  form?.addEventListener("submit", () => {
    if (form.checkValidity() && submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "Signing in…";
    }
  });
});
