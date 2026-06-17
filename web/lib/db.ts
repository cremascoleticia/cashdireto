/**
 * Pool Postgres (server-side apenas) — lê o Supabase via pooler em modo sessão.
 *
 * NUNCA importar em Client Components: usa credenciais de servidor (PG* em .env.local). As
 * variáveis PG* são lidas automaticamente pelo node-postgres; SSL é exigido pelo pooler do Supabase.
 * Singleton entre hot-reloads do Next (evita esgotar conexões em dev).
 */
import { Pool } from "pg";

const globalForPg = globalThis as unknown as { _pgPool?: Pool };

export const pool: Pool =
  globalForPg._pgPool ??
  new Pool({
    // host/porta/usuário/senha/dbname vêm de PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE
    ssl: { rejectUnauthorized: false }, // pooler Supabase exige TLS
    max: 5,
  });

if (process.env.NODE_ENV !== "production") globalForPg._pgPool = pool;

/** Query tipada simples; devolve as linhas. */
export async function consultar<T = Record<string, unknown>>(
  sql: string,
  params: unknown[] = [],
): Promise<T[]> {
  const res = await pool.query(sql, params);
  return res.rows as T[];
}
