const loginBtn = document.getElementById('login');
if (loginBtn) {
    loginBtn.addEventListener('click', ()=>{
        window.location.href = 'auth/x/login';
    });
}

if (typeof lucide !== 'undefined') {
    lucide.createIcons();
}

document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
  anchor.addEventListener("click", function (e) {
    e.preventDefault();
    const target = document.querySelector(this.getAttribute("href"));
    if (target) {
      target.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  });
});