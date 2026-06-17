/**
 * Bloco A — Cockpit de monitoramento (evolução diária da operação).
 *
 * A maioria dos indicadores depende de dados OPERACIONAIS que ainda não existem (operação, parcelas,
 * faturamento, repasse, extrato). Enquanto não chegam, ficam marcados "indisponível" (regra 9: nunca
 * estimar em silêncio). O que JÁ dá para mostrar de verdade: o status de ingestão dos arquivos
 * (core.fonte_arquivo) — base do painel P-A2 e da regra "evidência ausente = evidência negativa".
 */
import { consultar } from "./db";

export interface StatusIngestao {
  tipo: string;
  ultimaData: string | null;
  status: string | null;
  nArquivos: number;
}

/** P-A2 — status de ingestão por tipo de fonte (a partir do que foi carregado de verdade). */
export async function getStatusIngestao(): Promise<StatusIngestao[]> {
  return consultar<StatusIngestao>(`
    select tipo,
           to_char(max(data_referencia), 'YYYY-MM-DD') as "ultimaData",
           max(status) as status,
           count(*)::int as "nArquivos"
    from core.fonte_arquivo
    group by tipo
    order by tipo`);
}

export interface OperacaoResumo {
  id: string;
  cedente_grupo: string;
}

/** Lista de operações cadastradas (hoje vazio — Bloco A aguarda esse dado). */
export async function getOperacoes(): Promise<OperacaoResumo[]> {
  return consultar<OperacaoResumo>(
    "select id::text, cedente_grupo from core.operacao order by criado_em",
  );
}

/** Definição de cada KPI do cockpit + a fonte de dado de que depende (para a UI explicar o vazio). */
export const KPIS_COCKPIT = [
  { chave: "saldo_devedor", titulo: "Saldo devedor", depende: "operação" },
  { chave: "lastro_travado", titulo: "Lastro travado", depende: "ur_efeitos + horizonte da operação" },
  { chave: "razao_garantia", titulo: "Razão de Garantia (RG)", depende: "operação (saldo devedor + RG mínimo)" },
  { chave: "faturamento_30d", titulo: "Faturamento médio 30d", depende: "faturamento_diario" },
  { chave: "repasse_dia", titulo: "Repasse do dia", depende: "repasse_diario" },
  { chave: "diluicao_30d", titulo: "Diluição 30d", depende: "faturamento_diario (diluição)" },
] as const;

export const GRAFICOS_COCKPIT = [
  { titulo: "G-A1 · Razão de Garantia × gatilho mínimo", depende: "operação + série de lastro" },
  { titulo: "G-A2 · Faturamento diário + média móvel 7d", depende: "faturamento_diario" },
  { titulo: "G-A3 · Concentração por credenciadora", depende: "faturamento_diario" },
] as const;
