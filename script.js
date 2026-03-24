function loadLogo(input) {
  const file = input.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function () {
    localStorage.setItem("siteLogo", reader.result);
    displayLogo();
  };
  reader.readAsDataURL(file);
}

function displayLogo() {
  const logoData = localStorage.getItem("siteLogo");
  if (logoData) {
    document.querySelectorAll(".logo-preview").forEach(img => {
      img.src = logoData;
      img.style.display = "block";
    });
  }
}

window.onload = displayLogo;
