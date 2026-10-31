// Lista de canciones del Reproductor de Música.
// Generado por tools/music_player.py, pero también se puede editar a mano:
//   sonido   -> el nombre del sonido en MusicPlayer_RP/sounds/sound_definitions.json
//   nombre   -> lo que sale en el menú
//   segundos -> lo que dura (para saber cuándo termina; 0 = no se sabe)

export const AJUSTES = {
  volumen: 1.0,
  oyentes_por_defecto: "yo",
  callar_musica_vanilla: true,
  mostrar_titulo: true
};

export const CANCIONES = [
  {"sonido": "musica.arctic", "nombre": "Arctic", "segundos": 69.83},
  {"sonido": "musica.feel_nothing_v2", "nombre": "Feel Nothing V2", "segundos": 164.77, "autor": "Eternity OST"},
  {"sonido": "musica.parfum_d_etoiles", "nombre": "Parfum d'étoiles", "segundos": 172.74},
  {"sonido": "musica.dreaming_of_you_cathedral", "nombre": "Dreaming of You (Cathedral)", "segundos": 178.42, "autor": "Selena (432 Hz)"},
  {"sonido": "musica.feel_the_fury", "nombre": "Feel The Fury", "segundos": 233.06, "autor": "Sonic.exe: Outcome Memories OST"},
  {"sonido": "musica.pradera_tranquila", "nombre": "Pradera Tranquila", "segundos": 59.0, "autor": "Demo"},
  {"sonido": "musica.noche_estrellada", "nombre": "Noche Estrellada", "segundos": 32.76, "autor": "Demo"},
];
