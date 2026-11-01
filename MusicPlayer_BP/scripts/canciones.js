// Lista de canciones del Reproductor de Música.
// Generado por tools/music_player.py, pero también se puede editar a mano:
//   sonido   -> el nombre del sonido en MusicPlayer_RP/sounds/sound_definitions.json
//   nombre   -> lo que sale en el menú
//   segundos -> lo que dura (para saber cuándo termina; 0 = no se sabe)
//   final, segundos_final -> (opcional) el sonido con los últimos segundos, para el botón Finalizar.
//                           Si no lo tiene, Finalizar la para de golpe como Detener.

export const AJUSTES = {
  volumen: 1.0,
  oyentes_por_defecto: "yo",
  callar_musica_vanilla: true
};

export const CANCIONES = [
  {"sonido": "musica.arctic", "nombre": "Arctic", "segundos": 69.83, "final": "musica.arctic.final", "segundos_final": 10.0},
  {"sonido": "musica.feel_nothing_v2", "nombre": "Feel Nothing V2", "segundos": 164.77, "final": "musica.feel_nothing_v2.final", "segundos_final": 10.0, "autor": "Eternity OST"},
  {"sonido": "musica.parfum_d_etoiles", "nombre": "Parfum d'étoiles", "segundos": 172.74, "final": "musica.parfum_d_etoiles.final", "segundos_final": 10.0},
  {"sonido": "musica.dreaming_of_you_cathedral", "nombre": "Dreaming of You (Cathedral)", "segundos": 178.42, "final": "musica.dreaming_of_you_cathedral.final", "segundos_final": 10.0, "autor": "Selena (432 Hz)"},
  {"sonido": "musica.feel_the_fury", "nombre": "Feel The Fury", "segundos": 233.06, "final": "musica.feel_the_fury.final", "segundos_final": 10.0, "autor": "Sonic.exe: Outcome Memories OST"},
  {"sonido": "musica.even_gods_can_bleed", "nombre": "Even Gods Can Bleed", "segundos": 184.96, "final": "musica.even_gods_can_bleed.final", "segundos_final": 10.0, "autor": "Sonic.exe: Outcome Memories (Johnny Joymode & 2011x)"},
  {"sonido": "musica.concrete_coffin", "nombre": "Concrete Coffin", "segundos": 146.37, "final": "musica.concrete_coffin.final", "segundos_final": 9.98},
  {"sonido": "musica.trainride_trouble", "nombre": "Trainride Trouble", "segundos": 86.44, "final": "musica.trainride_trouble.final", "segundos_final": 10.0, "autor": "Sonic.exe: Outcome Memories (Mirage Saloon, unused)"},
  {"sonido": "musica.mirage_saloon_final_80", "nombre": "Mirage Saloon Final 80", "segundos": 80.85, "final": "musica.mirage_saloon_final_80.final", "segundos_final": 10.0, "autor": "Sonic.exe: Outcome Memories (_astranovayt)"},
  {"sonido": "musica.construction", "nombre": "Construction", "segundos": 69.81, "final": "musica.construction.final", "segundos_final": 10.0, "autor": "Darkest Hours OST (TheRagdolls Chase)"},
  {"sonido": "musica.christmas_kids", "nombre": "Christmas Kids", "segundos": 136.19, "final": "musica.christmas_kids.final", "segundos_final": 10.0},
  {"sonido": "musica.ff9cae", "nombre": "FF9CAE (Color and Electricity)", "segundos": 113.1, "final": "musica.ff9cae.final", "segundos_final": 10.0, "autor": "Forsaken OST (c00lkidd)"},
  {"sonido": "musica.respite_waxing_damnation", "nombre": "Respite, Waxing Damnation", "segundos": 120.63, "final": "musica.respite_waxing_damnation.final", "segundos_final": 10.0, "autor": "NoLongerNull & beatimesfive"},
  {"sonido": "musica.your_new_forever", "nombre": "Your New Forever", "segundos": 121.55, "final": "musica.your_new_forever.final", "segundos_final": 10.0, "autor": "Eternity Lobby Theme"},
  {"sonido": "musica.pradera_tranquila", "nombre": "Pradera Tranquila", "segundos": 59.0, "final": "musica.pradera_tranquila.final", "segundos_final": 10.0, "autor": "Demo"},
  {"sonido": "musica.noche_estrellada", "nombre": "Noche Estrellada", "segundos": 32.76, "final": "musica.noche_estrellada.final", "segundos_final": 10.0, "autor": "Demo"},
];
