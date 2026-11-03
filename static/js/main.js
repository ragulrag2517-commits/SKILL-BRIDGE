document.addEventListener('DOMContentLoaded', function () {
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(function (alertElement) {
    setTimeout(function () {
      if (alertElement && alertElement.parentNode) {
        alertElement.remove();
      }
    }, 4000);
  });
});
