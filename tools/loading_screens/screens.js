// The loading screens. Each one is shown by a title made only of formatting codes
// (`marker`: invisible on its own); the resource pack's HUD draws the screen while
// that title is up, and shows the subtitle as the tip.
export const SCREENS = [
    { id: "siluetas", name: "Siluetas", marker: "§l§o§a§d§2§r", boss: "all" },
    { id: "dibujo", name: "Tras la batalla", marker: "§l§o§a§d§3§r", boss: "all" },
    { id: "ignis", name: "Ignis: la batalla", marker: "§l§o§a§d§1§r", boss: "Ignis" },
];

// Boss tips: a screen shows its own boss' tips ("all": any boss).
export const TIPS = [
    ["Ignis", "Ignis solo se cura con golpes de espada: no dejes que te alcance seguido."],
    ["Ignis", "La marca ardiente se acumula hasta 5 veces. Aléjate unos segundos para que se apague."],
    ["Ignis", "Devuélvele las bolas de fuego del abismo de un golpe para agrietar su escudo."],
    ["Ignis", "Cuando aparece la gran runa azul bajo sus pies, sal de las filas de sigilos."],
    ["Ignis", "En las fases de alma, la gran runa lanza sigilos en 8 direcciones."],
    ["Ignis", "Los círculos repartidos no siguen ningún orden: busca los huecos entre ellos."],
    ["Ignis", "Su estocada empaladora llega lejos: esquiva hacia un lado, no hacia atrás."],
    ["Ignis", "Si salta hacia ti, muévete: te sigue en el aire y aterriza con fuerza."],
    ["Ignis", "Los Escuderos de Piedra Negra no sufren sus ataques: derríbalos tú."],
    ["Ignis", "Ningún golpe le quita más de 20 de vida a Ignis: ataca seguido, no fuerte."],
    ["Ignis", "Ofrece Ceniza Ardiente en el Altar de Fuego para despertar a Ignis."],
    ["Ignis", "Por debajo de un tercio de vida Ignis entra en furia: guarda tus pociones para ese momento."],
    ["Nether", "El Señor del Nether despierta con un cráneo de esqueleto wither en el Altar de Almas."],
    ["Nether", "Por debajo de la mitad de vida, el Señor del Nether llama a más Caballeros de Almas."],
    ["Nether", "Los Caballeros de Almas marchitan con cada golpe: lleva leche."],
    ["Nether", "La Fortaleza de Almas solo aparece en los valles de arena de almas."],
    ["Ender", "El Endersent suelta un Ojo de Ender Encantado al morir."],
    ["Ender", "Seis Ojos de Ender Encantados abren el camino al Corazón Vengativo del Ender."],
];

export const tipsFor = (screen) => TIPS.filter(([boss]) => screen.boss === "all" || boss === screen.boss).map(([, t]) => t);
