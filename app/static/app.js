document.body.addEventListener("htmx:beforeSwap", (event) => {
  if (event.detail.xhr.status === 403) {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
});

document.body.addEventListener("htmx:afterSettle", (event) => {
  const alvo = event.detail.target;
  if (!alvo?.matches("#painel-host, #painel-dia")) {
    return;
  }

  const dialog = document.querySelector("#painel-host #painel-dia");
  if (dialog && !dialog.open) {
    dialog.showModal();
  }
});
