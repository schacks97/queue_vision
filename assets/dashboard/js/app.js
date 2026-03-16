/** Notification using bootstrap toast */
document.addEventListener("DOMContentLoaded", function () {
  // Initialize toasts
  const toastElements = document.querySelectorAll(".toast");
  console.log("Toast elements found:", toastElements.length);
  toastElements.forEach((element) => {
    const toast = new bootstrap.Toast(element, {
      autohide: true,
      delay: 5000,
    });
    toast.show();
    console.log("Toast shown:", element);
  });

  // Initialize tooltips
  const tooltipTriggerList = document.querySelectorAll(
    '[data-bs-toggle="tooltip"]',
  );
  [...tooltipTriggerList].map(
    (tooltipTriggerEl) => new bootstrap.Tooltip(tooltipTriggerEl),
  );
});
/** ----------------------- **/
