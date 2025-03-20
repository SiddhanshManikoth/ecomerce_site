
    document.addEventListener('DOMContentLoaded', function() {
      // Get the toast element
      const toastElement = document.getElementById('liveToast');
      const toast = new bootstrap.Toast(toastElement);

      // Get the button that triggers the toast
      const toastButton = document.getElementById('liveToastBtn');

      // Add click event to button to show toast
      toastButton.addEventListener('click', function() {
        toast.show();
      });
    });
