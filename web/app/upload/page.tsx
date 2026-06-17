"use client";

/**
 * Upload de arquivos CERC → ingestão. Envia para /api/processar (que chama o CLI Python),
 * mostra "Processando…" enquanto roda e lista o resultado por arquivo. Sem <form> submit nativo —
 * usa fetch + estado, pra controlar o feedback (arquivos grandes levam alguns segundos).
 */
import Link from "next/link";
import { useState } from "react";

interface Resultado {
  ok?: boolean;
  tipo?: string;
  nome_arquivo?: string;
  data_referencia?: string;
  erro?: string;
}

export default function UploadPage() {
  const [arquivos, setArquivos] = useState<FileList | null>(null);
  const [processando, setProcessando] = useState(false);
  const [resultados, setResultados] = useState<Resultado[] | null>(null);
  const [erros, setErros] = useState<Resultado[] | null>(null);
  const [falha, setFalha] = useState<string | null>(null);

  async function enviar() {
    if (!arquivos?.length) return;
    setProcessando(true);
    setResultados(null);
    setErros(null);
    setFalha(null);
    try {
      const fd = new FormData();
      Array.from(arquivos).forEach((f) => fd.append("arquivos", f));
      const resp = await fetch("/api/processar", { method: "POST", body: fd });
      const data = await resp.json();
      setResultados(data.resultados ?? []);
      setErros(data.erros ?? []);
    } catch (e) {
      setFalha(e instanceof Error ? e.message : "falha de rede");
    } finally {
      setProcessando(false);
    }
  }

  return (
    <main className="max-w-3xl mx-auto p-6 flex flex-col gap-5">
      <h1 className="text-2xl font-semibold text-slate-800">Upload de arquivos CERC</h1>
      <p className="text-slate-600 text-sm">
        Suba os arquivos de retorno (AP005, etc.). O sistema detecta a fonte pelo nome, parseia e
        carrega no banco (idempotente por <code>sha256</code> — reenviar não duplica). Depois os
        indicadores aparecem nas telas.
      </p>

      <div className="bg-white rounded-xl shadow p-6 flex flex-col gap-4">
        <input
          type="file"
          multiple
          accept=".csv,.html,.htm"
          disabled={processando}
          onChange={(e) => setArquivos(e.target.files)}
          className="block w-full text-sm border border-slate-300 rounded-lg p-2"
        />
        <button
          onClick={enviar}
          disabled={processando || !arquivos?.length}
          className="bg-slate-900 text-white rounded-lg px-4 py-2 w-fit hover:bg-slate-700 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {processando ? "Processando…" : "Processar"}
        </button>

        {processando && (
          <div className="flex items-center gap-3 rounded-lg border border-amber-300 bg-amber-50 text-amber-800 px-4 py-3">
            <svg className="animate-spin h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            <span className="text-sm">
              Detectando a fonte, parseando e carregando. Arquivos grandes (AP005) podem levar alguns
              segundos — <b>não feche a página</b>.
            </span>
          </div>
        )}
      </div>

      {falha && <p className="text-red-700 text-sm">Erro na requisição: {falha}</p>}

      {resultados && (
        <div className="flex flex-col gap-3">
          {resultados.length > 0 && (
            <>
              <p className="text-emerald-700 text-sm">
                ✓ {resultados.length} arquivo(s) carregado(s).{" "}
                <Link className="underline" href="/garantia">
                  Ver indicadores →
                </Link>
              </p>
              <table className="w-full text-sm bg-white rounded-xl shadow overflow-hidden">
                <thead className="bg-slate-100 text-left text-slate-600">
                  <tr>
                    <th className="p-2">Arquivo</th>
                    <th className="p-2">Fonte</th>
                    <th className="p-2">Data de referência</th>
                  </tr>
                </thead>
                <tbody>
                  {resultados.map((r, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="p-2">{r.nome_arquivo}</td>
                      <td className="p-2 font-medium">{r.tipo}</td>
                      <td className="p-2">{r.data_referencia}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {erros?.map((e, i) => (
            <p key={i} className="text-red-700 text-sm">
              ✗ {e.nome_arquivo ?? "arquivo"}: {e.erro}
            </p>
          ))}
          {!resultados.length && !erros?.length && <p className="text-slate-500 text-sm">Nada processado.</p>}
        </div>
      )}
    </main>
  );
}
