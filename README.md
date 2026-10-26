# Addons de mobs para Minecraft Bedrock

| Addon | Descarga | Generador |
|---|---|---|
| **The Revamp of the Soul** (antes Soul Corrupted Mobs; base de Euforia) | [`dist/TheRevampOfTheSoul.mcaddon`](dist/TheRevampOfTheSoul.mcaddon) | `tools/soul_mobs.py` |
| **Medieval Mobs** – mobs medievales | [`dist/MedievalMobs.mcaddon`](dist/MedievalMobs.mcaddon) | `tools/generate.py` |
| **Ruleta de Colores** – ruleta en el HUD con comandos de administrador | [`dist/Roulette.mcaddon`](dist/Roulette.mcaddon) | `tools/roulette.py` |

Abre el `.mcaddon` y activa el pack *Behavior* en el mundo; el de recursos se añade solo. No hace falta activar experimentos.

- The Revamp of the Soul requiere Minecraft Bedrock **1.26.0** o superior.
- Medieval Mobs requiere **1.21.0** o superior.
- Ruleta de Colores requiere **1.21.90** o superior.

---

# Ruleta de Colores

![La ruleta en cada color, el resultado oculto y la ruleta rota](docs/roulette_preview.png)

Ruleta de 6 colores (**rojo, verde, azul, blanco, celeste y amarillo**) con aspecto natural: borde de corteza,
lianas con hojas y flores, ramitas entre los colores y un tronco en el centro. Por defecto aparece
**encima de la barra de objetos**. Solo la maneja el administrador (operador) y lo que hace se aplica a todos los jugadores.

### El control de la ruleta

Cógelo del inventario creativo (*Control de la Ruleta*), con `/give @s roulette:controller` o con `/roulette:item`.
Al hacer **clic derecho** se abre un menú:

| Opción | Qué hace |
|---|---|
| Giro aleatorio | Gira y cae en un color al azar. |
| Girar a un color | Eliges el color y, si quieres, un **mensaje** que sale en la barra de acción al caer (ej. blanco → "¡Los creepers de azalea vienen!"). |
| Mostrar / Ocultar ruleta | Aparece creciendo desde muy pequeña, o se encoge hasta desaparecer. |
| Ocultar resultado | Deja todo en blanco con una **carita feliz** en blanco y negro en el centro. El siguiente giro vuelve a mostrar los colores. |
| Girar sin control | Sin resultado: empieza a girar despacio, cada vez más rápido hasta **10 veces** la velocidad normal, desaparece medio segundo y vuelve **rota por la mitad**. |
| Cambiar posición | Encima de la barra de objetos, debajo de la barra de hambre o en el centro. |

### Giro

- Antes de girar suenan **tres campanas de aviso**; luego gira durante **15 segundos**, frena poco a poco y suena un clic en cada color.
- Al parar suena un aviso y la ruleta se hace **1,5 veces más grande durante 1 segundo**.
- No se muestra ningún título ni mensaje en el chat con el resultado, solo el mensaje que hayas escrito (si lo hay).
- El resultado se guarda en el marcador `ruleta`, jugador `resultado`
  (1 rojo, 2 verde, 3 azul, 4 blanco, 5 celeste, 6 amarillo).

### Comandos

| Comando | Qué hace |
|---|---|
| `/spin_roulette:rojo` | Gira la ruleta y cae en rojo. También `:verde`, `:azul`, `:blanco`, `:celeste`, `:amarillo` y `:aleatorio`. |
| `/spin_roulette:blanco "Los creepers de azalea vienen"` | Igual, con mensaje al caer. |
| `/roulette:show` / `/roulette:hide` | Muestra / oculta la ruleta. |
| `/roulette:blank` | Oculta el resultado (todo en blanco con la carita). |
| `/roulette:wild` | Gira sin control hasta romperse. |
| `/roulette:pos_hotbar`, `/roulette:pos_hambre`, `/roulette:pos_centro` | Cambia la posición para todos. |
| `/roulette:item` | Te da el control de la ruleta. |

- Al final se puede añadir un selector de jugadores (`/roulette:show @a[tag=juego]`); sin él se aplica a todos.
  En `spin_roulette` el selector va después del mensaje.
- Con `/scriptevent` (bloques de comandos): `spin_roulette:rojo <mensaje>`, `roulette:show`, `roulette:hide`,
  `roulette:blank`, `roulette:wild`, `roulette:pos_hotbar`, `roulette:pos_hambre`, `roulette:pos_centro`.

### Aviso de tótem

Cuando un jugador gasta un tótem de la inmortalidad, sale en el chat para todos:
*[Totem] El jugador Steve ha consumido un totem*.

### Notas

- Es ligero: el script solo envía algo a un jugador cuando su ruleta cambia, y la interfaz solo calcula la posición activa.
- La ruleta se dibuja con JSON UI usando títulos ocultos que empiezan por `_roul:`; el resto de títulos se ve normal.
- El tamaño, las posiciones y las duraciones se cambian en `tools/roulette.py`
  (`UI_SIZE`, `POSITIONS`, `SPIN_TICKS`, `WILD_TICKS`...).

---|---|
| Giro aleatorio | Gira y cae en un color al azar. |
| Girar a un color | Eliges el color y, si quieres, un **mensaje** que sale al caer (ej. blanco → "¡Los creepers de azalea vienen!"). |
| Mostrar / Ocultar ruleta | Aparece creciendo desde muy pequeña, o se encoge hasta desaparecer. |
| Ocultar resultado | Deja todos los colores en blanco. El siguiente giro los vuelve a mostrar. |
| Activar PvP | Activa el PvP: la ruleta se cambia 5 s por **dos espadas cruzadas** y luego vuelve. |
| Desactivar PvP | Desactiva el PvP: la ruleta se cambia 5 s por **dos espadas separadas** y luego vuelve. |

### Comandos

| Comando | Qué hace |
|---|---|
| `/spin_roulette:rojo` | Gira la ruleta y cae en rojo. También `:verde`, `:azul`, `:blanco`, `:celeste`, `:amarillo` y `:aleatorio`. |
| `/spin_roulette:blanco "Los creepers de azalea vienen"` | Igual, con mensaje al caer. |
| `/roulette:show` / `/roulette:hide` | Muestra / oculta la ruleta. |
| `/roulette:blank` | Oculta el resultado (todo en blanco). |
| `/roulette:pvp_on` / `/roulette:pvp_off` | Activa / desactiva el PvP con las espadas. |
| `/roulette:item` | Te da el control de la ruleta. |

- Al final se puede añadir un selector de jugadores (`/roulette:show @a[tag=juego]`); sin él se aplica a todos.
  En `spin_roulette` el selector va después del mensaje.
- Con `/scriptevent` (bloques de comandos): `spin_roulette:rojo <mensaje>`, `roulette:show`, `roulette:hide`,
  `roulette:blank`, `roulette:pvp_on`, `roulette:pvp_off`.
- El giro dura **15 segundos**: da varias vueltas, frena poco a poco y suena un clic en cada color.
  Al parar, el color y el mensaje salen en grande en la pantalla y en el chat.
- El PvP se cambia con la regla del mundo `pvp`.
- El resultado se guarda en el marcador `ruleta`, jugador `resultado`
  (1 rojo, 2 verde, 3 azul, 4 blanco, 5 celeste, 6 amarillo).
- La ruleta se dibuja con JSON UI usando títulos ocultos que empiezan por `_roul:`; el resto de títulos se ve normal.
  El tamaño, la esquina, la posición y la duración del giro se cambian en `tools/roulette.py`
  (`UI_SIZE`, `ANCHOR`, `OFFSET`, `SPIN_TICKS`).

---|---|
| `/roulette:show` | Muestra la ruleta. |
| `/spin_roulette:rojo` | Gira la ruleta y la hace caer en rojo. Si estaba oculta, la muestra. |
| `/spin_roulette:verde`, `:azul`, `:blanco`, `:celeste`, `:amarillo` | Igual, con los otros colores. |
| `/spin_roulette:aleatorio` | Gira la ruleta y cae en un color al azar. |
| `/roulette:hide` | Oculta la ruleta. |

- Todos aceptan un selector de jugadores al final, por ejemplo `/spin_roulette:azul @a[tag=juego]`.
  Sin selector se aplican a todos los jugadores.
- Los mismos comandos funcionan con `/scriptevent` (por ejemplo en bloques de comandos):
  `/scriptevent spin_roulette:rojo`, `/scriptevent roulette:show` y `/scriptevent roulette:hide`.
- El giro dura 6 segundos: da varias vueltas, frena poco a poco y suena un clic en cada color.
  Al parar, el color sale en la barra de acción y en el chat.
- El resultado se guarda en el marcador `ruleta`, jugador `resultado`
  (1 rojo, 2 verde, 3 azul, 4 blanco, 5 celeste, 6 amarillo).
- Si un jugador sale y vuelve a entrar con la ruleta abierta, la vuelve a ver.
- La ruleta se dibuja con JSON UI usando títulos ocultos que empiezan por `_roul:`; el resto de títulos se ve normal.
  El tamaño, la esquina y la duración del giro se cambian en `tools/roulette.py` (`UI_SIZE`, `ANCHOR`, `SPIN_TICKS`).

---

# The Revamp of the Soul

![Todos los mobs con su outline](docs/soul_mobs_preview.png)

![Espada, esencia, núcleo, planta, estrella y altar](docs/soul_mobs_items.png)

La base es el addon original *Soul Corrupted Mobs v1.0.0*: sus texturas, el **outline blanco**,
las animaciones vanilla y los identificadores `eu_sc:`. Se guarda sin cambios en `sources/soul_corrupted_mobs_v1.0.0/`.
El generador `tools/soul_mobs.py` (con `tools/soul_bosses.py`) lo copia y le añade todo lo demás.

| Mob | IDs |
|---|---|
| Zombi de Alma Corrupta | `eu_sc:soul_corrupted_zombie` (azul, original) / `_red` / `_green` |
| Creeper de Alma Corrupta | `eu_sc:soul_corrupted_creeper` / `_red` / `_green` |
| Esqueleto de Alma Corrupta | `eu_sc:soul_corrupted_skeleton` / `_red` / `_green` |
| Phantom de Alma Corrupta (4 alas puntiagudas, 2,5 veces más grande) | `eu_sc:soul_corrupted_phantom` / `_red` / `_green` |
| Phantom de Alma Domable (montable) | `eu_sc:soul_corrupted_phantom_mount` |
| Esqueleto Wither de Alma Corrupta | `eu_sc:soul_corrupted_wither_skeleton` / `_red` / `_green` |
| Araña de Alma Corrupta (1,3 veces más grande, aspecto monstruoso) | `eu_sc:soul_corrupted_spider` / `_red` / `_green` |
| Zombi Invocador de Alma Corrupta (sombrero de granjero y capa) | `eu_sc:soul_corrupted_summoner` / `_red` / `_green` |
| **Sub-jefe**: Creeper Titán de Alma Corrupta (azul marino) | `eu_sc:soul_corrupted_creeper_titan` |
| Esqueleto Encapotado (variante vanilla, sin alma) | `eu_sc:caped_skeleton` |
| **Mini jefe**: Esqueleto Mutante de Alma Corrupta | `eu_sc:soul_mutant_skeleton` |
| **Mini jefe**: Zombi Cuchilla de Alma Corrupta | `eu_sc:soul_blade_zombie` |
| Altar de Curación | `eu_sc:healing_altar` |

### Progresión

1. Los mobs de alma sueltan **Esencia de Alma**: un 9 % de probabilidad, más con Botín. Todos los drops son un 75 % menos frecuentes.
2. **Planta de Alma Corrupta**: 4 esencias, hongo carmesí y tierra de almas. Úsala para invocar al **Zombi Cuchilla**.
3. El Zombi Cuchilla suelta el **Núcleo de Alma**.
4. **Estrella de Alma Corrupta**: 7 esencias, el núcleo y un diamante. Úsala para invocar al **Esqueleto Mutante**.
5. El Esqueleto Mutante suelta la **Espada de Alma Corrupta** (siempre).

### Mini jefes (sin barra de vida)

**Esqueleto Mutante (azul):**
- Usa el modelo de Mutant Creatures: modelo, textura recoloreada y animaciones, guardados en `sources/mutant_skeleton/`.
- Mide el doble que un jugador y tiene 400 de vida.
- Su espada mide unos 2,4 bloques: hoja ancha con filos blancos, guarda con puntas y pomo.
- Ataca con una espada gigante y hace un **slash épico**.
- De vez en cuando lanza una **explosión** que no rompe bloques: te empuja y te deja **ciego 3 s**.
- **Entrada**: cae del cielo, aterriza agachado y se levanta.
- **Muerte**: se arrodilla y se desploma. Después invoca un creeper y un zombi de alma.

**Zombi Cuchilla (rojo):**
- Tamaño de jugador, con cuchillas en vez de brazos.
- 400 de vida y velocidad 0,33.
- Su ataque normal es exagerado: echa las cuchillas atrás y se lanza con ellas hacia delante.
- **Explosión**: lentitud II 3 s.
- **Embestida**: si te alcanza, lentitud 255 durante 1 s.
- **Invoca zombis rojos** (máximo 4 cerca).
- **Entrada**: sale del suelo.
- **Muerte**: algo lo arrastra bajo tierra mientras se resiste.

### Nuevos mobs

**Araña de Alma Corrupta:**
- Ocho ojos blancos, colmillos, abdomen con púas y patas con garras.
- Trepa paredes y salta sobre el jugador.

**Zombi Invocador:**
- Cuando te ve invoca un zombi y un esqueleto de su mismo color: levanta los brazos y salen del suelo.
- Lo repite cada 30 s, y nunca si ya hay muchos mobs de alma cerca.

**Creeper Titán (sub-jefe):**
- Solo existe en azul marino, con outline. Más alto que un creeper y con patas largas: unos 2,25 bloques.
- Al aparecer provoca una mini explosión que no rompe bloques.
- Al explotar deja un creeper de alma celeste normal.
- Aparece rara vez, en el Overworld y en el Nether.

**Esqueleto Encapotado:**
- Un esqueleto vanilla, con su textura normal, que lleva capa y capucha.
- Dispara 2 flechas seguidas.

### Esqueleto Wither de Alma Corrupta

- Hay uno en cada color, más oscuro y con el tamaño normal de un wither skeleton (1,2 veces un esqueleto).
- Corre a 0,4 (el wither skeleton normal va a 0,25), con una carrera exagerada: inclinado y con los brazos hacia atrás.
- Su **slash** hace 60 de daño: mata de un golpe aunque lleves armadura de hierro completa.
- **Muere de un golpe** (1 de vida) y no suelta nada.

### Resto

- **Colores**: más suaves y apagados que antes, con el outline blanco. El altar y el phantom domable conservan sus colores.
- **Inclinación al ir hacia el objetivo**: el zombi se inclina un poco más que el creeper y el esqueleto, menos que los dos.

- **Al golpear**: Oscuridad, más un extra según el color:
  - azul: lentitud.
  - rojo: prende fuego.
  - verde: veneno.
- Las flechas de los esqueletos invocan rayos, en los tres colores.
- **Inmunes** a fuego, lava, magma, congelación, ahogamiento y wither. No se convierten en ahogados ni en *strays*.
- Caminan un 12 % más rápido que sus versiones vanilla.
- **Spawn natural**: los mobs de alma son aproximadamente **el 35 %** de los monstruos que aparecen en sus biomas. Las probabilidades de cada bioma se calculan a partir de cuánto aparecen ahí los mobs vanilla.
  - Azules: solo en el Nether (valle de arena de almas, bosque distorsionado y deltas de basalto).
  - Rojos: solo en el Nether (bosque carmesí y desiertos del Nether).
  - Verdes: solo en el Overworld, en cualquier bioma salvo sabanas y biomas fríos.
  - Phantoms: el 35 % de los phantoms vanilla (los del insomnio) se convierte en phantoms de alma verdes.
- **Oscuridad**: dura 2 segundos.
- **Phantoms**:
  - todos vuelan 1,65 veces más rápido;
  - el hostil detecta jugadores a 96 bloques, ataca cada 2-5 s y vuela a 6-12 bloques sobre ti;
  - el domable se domestica con huesos y se monta como el happy ghast, a 0,033 de velocidad (happy ghast: 0,016).
- **Altar de Curación**:
  - mide 2 bloques, es inmune a todo daño y siempre mira hacia el mismo lado;
  - a **12 bloques** o menos te lanza un rayo de partículas y te cura 1 de vida por segundo;
  - se recoge agachado + interactuar;
  - receta: `C F C / C M C / C C C` (C = pizarra profunda rocosa, F = farol de almas, M = manzana dorada).
- **Espada**: 9 de daño, Wither II + quemadura, daño en área, y lleva el tag `minecraft:is_sword`.

---

# Medieval Mobs

12 mobs **nuevos e independientes** (no reemplazan a los vanilla) inspirados en los
zombis, esqueletos, slimes, endermen y creepers, con aspecto medieval, modelos
propios y golpes que dejan **efectos negativos**.

![Vista previa (frente y espalda de cada mob)](docs/preview.png)

## Los mobs

Cada mob tiene su propio identificador, su huevo de generación, sus reglas de spawn y su botín.
Los efectos de la columna "Al golpear" se aplican en cada golpe, flecha o explosión.

| Mob | ID | Qué hace | Al golpear |
|---|---|---|---|
| Caballero Zombi Caído | `medieval:zombie_knight` | Yelmo con visor y cresta, armadura completa, tabardo con cruz y espada de hierro. Resiste el empuje | Lentitud II, Debilidad |
| Zombi Lanzaflechas | `medieval:zombie_archer` | **Lanza flechas a puñetazos**, en ráfagas de dos con sus guanteletes gigantes. Lleva carcaj y gorro con pluma | Veneno, Hambre |
| Zombi de la Peste | `medieval:zombie_plague` | Médico de la peste: máscara de pico, sombrero, túnica larga e incensario | Náusea, Veneno, Hambre II |
| Esqueleto Espadachín | `medieval:skeleton_swordsman` | **Cuerpo a cuerpo** con espada, escudo en el brazo, gambesón y casco de hierro | Debilidad, Lentitud |
| Esqueleto Arquero Real | `medieval:skeleton_longbowman` | **A distancia** con arco y flechas de lentitud. Capucha verde y carcaj | Lentitud II, Debilidad |
| Señor de la Guerra Esqueleto | `medieval:skeleton_warlord` | **Combina las dos**: arco de lejos y espada al acercarte (cambia solo). Corona, capa y armadura negra. Es raro | Wither (cuerpo a cuerpo), Debilidad (flechas), Ceguera, Lentitud II |
| Slime del Pantano | `medieval:bog_slime` | **Mucho más rápido** que un slime normal. Musgo y setas encima. Se divide al morir | Veneno, Lentitud |
| Slime Real | `medieval:royal_slime` | **Rápido**, dorado, con corona y capa. Vive bajo tierra y se divide al morir | Debilidad, Fatiga minera, Náusea |
| Espectro del End | `medieval:ender_wraith` | Enderman encapuchado con túnica rasgada. Ataca a los jugadores cercanos aunque no lo mires | Ceguera, Wither |
| Caballero del End | `medieval:ender_knight` | Yelmo de obsidiana con cuernos, armadura, capa y espada. Neutral como el vanilla | Lentitud, Fatiga minera II, Levitación |
| Creeper de Asedio | `medieval:siege_creeper` | **Ataca y explota a la vez**: al golpearte enciende la mecha y sigue pegando mientras se hincha. Casco y barril de TNT. Explosión más fuerte | Lentitud, Debilidad |
| Creeper Pestilente | `medieval:plague_creeper` | **Ataca y explota a la vez**. Capucha, hongos y pústulas | Veneno, Náusea, Hambre II |

## Spawneo

- **Natural**: salen de noche o en la oscuridad, como los monstruos vanilla y junto a ellos.
  - El Slime del Pantano sale en pantanos y manglares.
  - El Slime Real sale bajo tierra, por debajo de Y=40.
  - Los endermen medievales también salen en el End.
- **Generadores (spawners)**: usa el huevo del mob sobre un generador de monstruos.
  Funciona igual que con los huevos vanilla.
- **Comandos**: `/summon medieval:skeleton_warlord`.
- **Huevos**: están en el inventario creativo, en la sección de huevos de generación.

## Estructura del proyecto

```
TheRevampOfTheSoul_BP/  TheRevampOfTheSoul_RP/  The Revamp of the Soul (generado)
sources/mutant_skeleton/                      modelo de Mutant Creatures (con permiso)
sources/soul_corrupted_mobs_v1.0.0/           addon original (base)
MedievalMobs_BP/   MedievalMobs_RP/    addon medieval
Roulette_BP/       Roulette_RP/        ruleta de colores (generado)
tools/             generadores en Python (modelos + texturas + JSON)
dist/              los .mcaddon listos para instalar
```

Los packs se generan con Python 3 y Pillow. Para cambiar vida, daño, efectos, colores o modelos:

1. Edita las tablas al principio del generador:
   - The Revamp of the Soul: `COLORS`, `BASE_MOBS`, `PHANTOM` y `WITHER` en `tools/soul_mobs.py`, y `BOSSES` en `tools/soul_bosses.py`.
   - Medieval Mobs: `MOBS` en `tools/generate.py`, y los modelos en `tools/models.py`.
2. Ejecuta el generador:

```
python3 tools/soul_mobs.py --preview
python3 tools/generate.py --preview
python3 tools/roulette.py --preview
```

Cada uno vuelve a generar sus packs y su `.mcaddon`. `--preview` además actualiza las imágenes de `docs/`.
