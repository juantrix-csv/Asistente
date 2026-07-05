# Finance System — Padrino Digital

Sistema de gestión financiera personal: transacciones, presupuestos, ahorros,
deudas, y reglas de seguridad financiera.

## Tipos de Transacciones

| Tipo | Significado | Ejemplo |
|------|------------|---------|
| `expense` | Gasto | "Gasté $5,000 en verdulería" |
| `income` | Ingreso | "Cobré $200,000 de Nexios" |
| `transfer` | Transferencia entre cuentas | "Pasé $50,000 de la caja de ahorro a MercadoPago" |
| `adjustment` | Ajuste/corrección | "Ajuste de $2,000 por error en registro anterior" |

## Registro de Transacciones

Cada transacción tiene:

```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('income','expense','transfer','adjustment')),
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'ARS',
    category TEXT,
    account TEXT,
    business_area TEXT CHECK(business_area IN (
        'personal','Ascend','fletes','Nexios','Rastrojero','home-gym','otros'
    )),
    payment_method TEXT,
    date TEXT NOT NULL,
    description TEXT,
    recurring INTEGER DEFAULT 0,
    -- Campos de corrección
    correction_id INTEGER,              -- Referencia a la transacción corregida
    -- Campos de moneda original (para conversiones)
    original_currency TEXT,
    original_amount REAL,
    conversion_rate REAL,
    conversion_source TEXT,
    conversion_date TEXT
);
```

## Áreas de Negocio (`business_area`)

Separación de finanzas por proyecto/área:

| Área | Descripción |
|------|------------|
| `personal` | Gastos personales (supermercado, alquiler, servicios) |
| `Ascend` | Ingresos y gastos del proyecto Ascend |
| `fletes` | Ingresos y gastos de Fletes Ostrit |
| `Nexios` | Ingresos y gastos del proyecto Nexios |
| `Rastrojero` | Gastos de mantenimiento del Rastrojero |
| `home-gym` | Gastos e ingresos del home gym |
| `otros` | Otras áreas no categorizadas |

## Categorías de Gasto

```
alimentos       — Supermercado, verdulería, delivery
transporte      — Nafta, estacionamiento, transporte público
servicios       — Luz, agua, gas, internet, celular
vivienda        — Alquiler, expensas, reparaciones
salud           — Médico, medicamentos, obra social
educación       — Cursos, libros, suscripciones
ocio            — Salidas, cine, suscripciones
ropa            — Ropa, calzado
tecnología      — Hardware, software, hosting
vehículo        — Repuestos, mecánico, seguro, patente
impuestos       — Monotributo, ingresos brutos
ahorro          — Transferencias a cuentas de ahorro
otros           — Gastos no categorizados
```

## Presupuestos

```sql
CREATE TABLE budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    period TEXT NOT NULL CHECK(period IN ('monthly','weekly','annual')),
    limit_amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'ARS',
    warning_percent REAL DEFAULT 80    -- % del límite que dispara warning
);
```

### Sistema de Alertas

| % del límite | Nivel | Mensaje |
|:-----------:|-------|---------|
| < 80% | Normal | Sin alerta |
| ≥ 80% | ⚠️ Warning | "Llevás el 85% de tu presupuesto de {categoría}" |
| ≥ 100% | 🔴 Excedido | "Superaste tu presupuesto de {categoría} en {exceso}" |
| ≥ 120% | 🚨 Crítico | "¡{categoría} está al 120%! Revisá urgente." |

## Metas de Ahorro

```sql
CREATE TABLE savings_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    target_amount REAL NOT NULL,
    current_amount REAL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'ARS',
    deadline TEXT
);
```

Padrino monitorea el progreso y calcula el ritmo necesario:
- `current_amount / target_amount` → % de progreso
- `(target_amount - current_amount) / months_remaining` → ahorro mensual necesario

## Deudas

```sql
CREATE TABLE debts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    total_amount REAL NOT NULL,
    remaining_amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'ARS',
    creditor TEXT,
    interest_rate REAL,
    due_date TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paid','defaulted'))
);
```

## Las 7 Reglas de Finanzas (CRÍTICAS)

Estas reglas son **no negociables** — Padrino las aplica siempre:

### 1. NUNCA mover dinero
Padrino no puede transferir, pagar, ni mover dinero. Solo registra.

### 2. NUNCA conectar cuentas bancarias (MVP)
En esta fase, Padrino no se conecta a APIs bancarias. Todos los datos se ingresan manualmente.

### 3. No asumir que ingreso del negocio = ganancia personal
Si un negocio factura $100,000, eso NO significa que Juan tenga $100,000 para gastar.
Hay que restar costos, impuestos, y reinversión.

### 4. No mezclar transferencias con ingresos/gastos
Pasar plata de una cuenta a otra NO es un ingreso ni un gasto. Es una transferencia.

### 5. Mantener moneda original en conversiones
Si se registra un gasto en USD pero la cuenta está en ARS, guardar:
- `original_currency: USD`
- `original_amount: 100`
- `conversion_rate: 1250`
- `amount: 125000` (en ARS)

### 6. NUNCA dar consejo financiero como certeza
Toda proyección, recomendación o análisis financiero DEBE incluir:
> "Esto es informativo, no constituye asesoramiento financiero. Revisá con un contador."

### 7. Correcciones vía reversal entries, NUNCA edits directos
Si un gasto se registró mal, NO se edita el registro original. Se crea una
transacción de tipo `adjustment` con `correction_id` apuntando a la original.

## Exportación

```bash
# CSV con UTF-8 BOM (compatible con Excel)
bash padrino/scripts/export.sh finance --from 2026-06-01 --to 2026-06-30

# Con filtro por área de negocio
bash padrino/scripts/export.sh finance --from 2026-01-01
```

El CSV incluye: id, type, amount, currency, category, account, business_area,
payment_method, date, description, recurring, original_currency, original_amount,
conversion_rate, created_at.

## Comandos

| Comando | Acción |
|---------|--------|
| `/gasto {monto} {desc}` | Registrar gasto |
| `/ingreso {monto} {desc}` | Registrar ingreso |
| `/finanzas` | Resumen financiero del mes |
| `/presupuesto` | Estado de presupuestos |
| `/ahorro` | Metas de ahorro |
| `/deudas` | Estado de deudas |
| `/exportar finanzas` | Exportar a CSV |

## Lenguaje Natural

```
"Gasté $5,000 en la verdulería"
→ type: expense, amount: 5000, category: alimentos, business_area: personal

"Cobré $200,000 de Nexios"
→ type: income, amount: 200000, business_area: Nexios

"Le cargué $15,000 de nafta al Rastrojero"
→ type: expense, amount: 15000, category: transporte, business_area: Rastrojero
```
