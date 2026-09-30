document.addEventListener("DOMContentLoaded", () => {
  const quitar = (aviso) => {
    aviso.classList.add("aviso--oculto");
    setTimeout(() => aviso.remove(), 300);
  };
  document.querySelectorAll(".avisos .aviso").forEach((aviso) => {
    const boton = aviso.querySelector(".aviso__cerrar");
    if (boton) {
      boton.addEventListener("click", () => quitar(aviso));
    }
    if (!aviso.classList.contains("aviso--error") && !aviso.classList.contains("aviso--warning")) {
      setTimeout(() => quitar(aviso), 6000);
    }
  });
});
