/**
 * Route handler de ingestão: recebe os arquivos do upload, salva temporariamente e chama o CLI
 * Python (cashdireto_worker.ingest_cli) que parseia e carrega no banco. Devolve resultados/erros.
 *
 * Roda só no servidor (runtime nodejs). PYTHON_BIN/WORKER_DIR vêm do .env.local (padrões locais).
 * Em Vercel isto NÃO funciona (sem runtime Python) — lá a ingestão precisaria de um serviço próprio.
 */
import { execFile } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const execFileP = promisify(execFile);
const PYTHON = process.env.PYTHON_BIN ?? "C:/Users/iziap/anaconda3/python.exe";
const WORKER = process.env.WORKER_DIR ?? "C:/Users/iziap/cashdireto/worker";

function ultimaLinhaJson(saida: string): unknown {
  const linha = saida.trim().split(/\r?\n/).filter(Boolean).pop() ?? "{}";
  return JSON.parse(linha);
}

export async function POST(req: Request) {
  const form = await req.formData();
  const arquivos = form.getAll("arquivos").filter((f): f is File => f instanceof File);
  if (!arquivos.length) {
    return NextResponse.json({ resultados: [], erros: [{ erro: "Nenhum arquivo enviado." }] }, { status: 400 });
  }

  const resultados: unknown[] = [];
  const erros: unknown[] = [];

  for (const file of arquivos) {
    const dir = await mkdtemp(join(tmpdir(), "cashdireto-"));
    const tmp = join(dir, file.name || "arquivo");
    try {
      await writeFile(tmp, Buffer.from(await file.arrayBuffer()));
      const { stdout } = await execFileP(
        PYTHON,
        ["-m", "cashdireto_worker.ingest_cli", tmp, file.name],
        { cwd: WORKER, maxBuffer: 64 * 1024 * 1024, timeout: 180_000 },
      );
      const r = ultimaLinhaJson(stdout) as { ok?: boolean };
      if (r.ok) resultados.push(r);
      else erros.push(r);
    } catch (e) {
      // o CLI sai com código 1 e imprime {"erro": ...} no stdout
      const err = e as { stdout?: string; message?: string };
      try {
        erros.push(ultimaLinhaJson(err.stdout ?? ""));
      } catch {
        erros.push({ nome_arquivo: file.name, erro: err.message ?? "falha ao processar" });
      }
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  }

  return NextResponse.json({ resultados, erros });
}
