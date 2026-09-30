document.addEventListener("DOMContentLoaded", () => {
  const tipo = document.getElementById("id_tipo");
  const origen = document.getElementById("id_cuenta_origen");
  const destino = document.getElementById("id_cuenta_destino");
  if (!tipo || !origen || !destino) {
    return;
  }
  const reglas = {
    DEPOSITO: [false, true],
    RETIRO: [true, false],
    TRANSFERENCIA: [true, true],
  };
  const actualizar = () => {
    const [usaOrigen, usaDestino] = reglas[tipo.value] || [true, true];
    [[origen, usaOrigen], [destino, usaDestino]].forEach(([campo, visible]) => {
      campo.closest(".grupo").hidden = !visible;
      if (!visible) {
        campo.value = "";
      }
    });
  };
  tipo.addEventListener("change", actualizar);
  actualizar();
});
