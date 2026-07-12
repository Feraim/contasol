"""Parser del cuaderno 43 de la AEB (extractos bancarios normalizados).

Cubre los registros de movimiento (22) y su ampliación de concepto (23),
que es lo necesario para la conciliación bancaria. No procesa el
registro de cabecera de cuenta (11) ni los de totales (33/88): son
informativos y no afectan a los movimientos importados. Algunos bancos
usan variantes ligeras de este formato; revisa los importes tras
importar.
"""

from dataclasses import dataclass, field
from datetime import date

from fastapi import HTTPException


@dataclass
class MovimientoN43:
    fecha_operacion: date
    fecha_valor: date
    concepto_comun: str
    concepto_propio: str
    importe: int  # céntimos, con signo: + abono/ingreso, - cargo/gasto
    documento: str
    referencia1: str
    referencia2: str
    concepto_ampliado: str = field(default="")

    @property
    def concepto(self) -> str:
        partes = [self.referencia1, self.referencia2, self.concepto_ampliado]
        return " ".join(p for p in partes if p).strip() or f"{self.concepto_comun}{self.concepto_propio}"


def _fecha(aammdd: str) -> date:
    aa, mm, dd = int(aammdd[0:2]), int(aammdd[2:4]), int(aammdd[4:6])
    anio = 2000 + aa if aa < 80 else 1900 + aa
    return date(anio, mm, dd)


def parsear(contenido: str) -> list[MovimientoN43]:
    movimientos: list[MovimientoN43] = []
    actual: MovimientoN43 | None = None
    for numero, linea_bruta in enumerate(contenido.splitlines(), start=1):
        linea = linea_bruta.rstrip("\r\n")
        if len(linea) < 2:
            continue
        codigo = linea[0:2]
        if codigo == "22":
            if len(linea) < 80:
                raise HTTPException(422, f"Línea {numero}: registro de movimiento incompleto (norma 43)")
            if actual is not None:
                movimientos.append(actual)
            try:
                importe = int(linea[28:42])
            except ValueError as exc:
                raise HTTPException(422, f"Línea {numero}: importe inválido") from exc
            signo = -1 if linea[27:28] == "1" else 1
            actual = MovimientoN43(
                fecha_operacion=_fecha(linea[10:16]),
                fecha_valor=_fecha(linea[16:22]),
                concepto_comun=linea[22:24].strip(),
                concepto_propio=linea[24:27].strip(),
                importe=signo * importe,
                documento=linea[42:52].strip(),
                referencia1=linea[52:64].strip(),
                referencia2=linea[64:80].strip(),
            )
        elif codigo == "23" and actual is not None:
            texto = linea[4:].strip()
            actual.concepto_ampliado = f"{actual.concepto_ampliado} {texto}".strip()
    if actual is not None:
        movimientos.append(actual)
    if not movimientos:
        raise HTTPException(422, "No se ha encontrado ningún movimiento (registro 22) en el fichero")
    return movimientos
