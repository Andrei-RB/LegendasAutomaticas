// Aplica o tema salvo antes da primeira pintura; o padrão é escuro.
try {
  var salvo = JSON.parse(localStorage.getItem("viraliza.tema") || "null");
  var tema = salvo && salvo.state && salvo.state.tema === "claro" ? "claro" : "escuro";
  document.documentElement.classList.toggle("dark", tema === "escuro");
} catch (erro) {
  document.documentElement.classList.add("dark");
}
