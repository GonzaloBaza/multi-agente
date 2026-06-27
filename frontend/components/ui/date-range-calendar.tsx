"use client";

/**
 * Calendario de rango (inline) para el filtro de Fechas del inbox.
 *
 * Se renderiza dentro de la sección "Fechas" del menú de filtros (embudo).
 * Usa react-day-picker en `mode="range"` y mapea a/desde strings "YYYY-MM-DD"
 * (los mismos que consumen el filtro de conversaciones y el export CSV vía
 * date_from/date_to). El tema oscuro se aplica con `.rdp-msk` (ver globals.css).
 */

import { DayPicker, type DateRange } from "react-day-picker";
import { format, isValid, parse } from "date-fns";
import { es } from "date-fns/locale";

type Props = {
  /** "YYYY-MM-DD" o "" */
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
};

const toStr = (d?: Date) => (d ? format(d, "yyyy-MM-dd") : "");

const toDate = (s: string): Date | undefined => {
  if (!s) return undefined;
  const d = parse(s, "yyyy-MM-dd", new Date());
  return isValid(d) ? d : undefined;
};

export function DateRangeCalendar({ from, to, onChange }: Props) {
  const selected: DateRange | undefined =
    from || to ? { from: toDate(from), to: toDate(to) } : undefined;

  return (
    <div className="rdp-msk px-1 pb-2 pt-1">
      <DayPicker
        mode="range"
        locale={es}
        numberOfMonths={1}
        defaultMonth={selected?.from}
        selected={selected}
        onSelect={(range) => onChange(toStr(range?.from), toStr(range?.to))}
      />
      {(from || to) && (
        <button
          type="button"
          onClick={() => onChange("", "")}
          className="mt-1 w-full text-[11px] text-fg-dim hover:text-fg"
        >
          Limpiar fechas
        </button>
      )}
    </div>
  );
}
