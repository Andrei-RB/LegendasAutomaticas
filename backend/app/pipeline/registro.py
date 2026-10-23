from app.pipeline.etapas.exemplo import EXEMPLO, EXEMPLO_GPU
from app.pipeline.executor import RegistroEtapas

registro_padrao = RegistroEtapas()
for _etapa in (EXEMPLO, EXEMPLO_GPU):
    registro_padrao.registrar(_etapa)
