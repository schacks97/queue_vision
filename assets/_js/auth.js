document.addEventListener('DOMContentLoaded', function() {
  const togglePasswords = document.querySelectorAll('.toggle-password');
  togglePasswords.forEach(function(togglePassword) {
    togglePassword.addEventListener('click', function() {
      const passwordField = this.previousElementSibling;
      const type = passwordField.getAttribute('type') === 'password' ? 'text' : 'password';
      passwordField.setAttribute('type', type);
      this.querySelector('i').classList.toggle('fa-eye');
      this.querySelector('i').classList.toggle('fa-eye-slash');
    });
  });
});