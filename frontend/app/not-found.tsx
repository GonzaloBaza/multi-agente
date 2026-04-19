/**
 * 404 consistente — se muestra cuando Next.js no matchea una ruta.
 * Mejor que el default del framework que es un texto plano sin estilo.
 */
import Link from "next/link";

export default function NotFound() {
  return (
    <div className="h-screen flex items-center justify-center bg-bg text-fg p-6">
      <div className="max-w-md text-center space-y-4">
        <div className="text-5xl">🕳️</div>
        <h1 className="text-lg font-semibold">Ruta no encontrada</h1>
        <p className="text-sm text-fg-dim">
          Esta URL no existe (o ya no existe). Probá navegar desde el inbox.
        </p>
        <Link
          href="/inbox"
          className="inline-block px-3 py-1.5 rounded bg-accent text-white text-xs font-medium hover:bg-accent-2"
        >
          Ir al inbox
        </Link>
      </div>
    </div>
  );
}
