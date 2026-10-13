# Definizioni degli episodi (prompt Seedance ottimizzati). Un episodio = un dizionario.
# Blocchi comuni riusati da tutti gli episodi del canale Luna, Leo & Stellina.

CAM_FIXED = ("static locked-off camera: no camera movement, no zoom, no push-in. The very first frame already has the final "
             "framing described below and it never changes.")

def HEADER(d, camera=None):
    cam = camera or CAM_FIXED
    return (f"A {d}-second vertical 9:16 animated short for toddlers. ONE continuous take at the children's eye level, no cuts. "
            f"CAMERA: {cam}")

FRAMING = ("FRAMING: medium-wide shot. The children are BIG in the frame: their full bodies fill about half of the frame height, "
           "feet at about 8% from the bottom edge, standing close together near the center. Only a thin strip of ground is visible "
           "below their feet. STELLINA floats at the height of their helmets, about as big as Luna's helmet.")
FRAMING_SOLO = ("FRAMING: medium-wide shot. {who} is BIG in the frame: full body filling about half of the frame height, feet at about "
                "8% from the bottom edge, near the center. STELLINA floats next to {obj} at helmet height, about as big as the helmet.")

STYLE = ("STYLE: simple preschool TV 3D cartoon style, soft vinyl-toy look, flat diffuse matte shading, bright even lighting, very soft "
         "minimal shadows, smooth low-detail textures, clean saturated cheerful colors, simple rounded shapes. Exactly the rendering of "
         "the reference images. The characters are fully 3D and move their whole bodies naturally.")

LUNA = ("- LUNA = the little astronaut girl from {img}: two dark-brown hair buns with coral ties poking out of her white helmet, coral "
        "accents. She wears the same one-piece astronaut jumpsuit as in the sheet: coral stripes down the sides of the arms and legs, "
        "coral knee pads, coral chest button. NO skirt, NO tutu, NO dress.")
LEO = ("- LEO = the little astronaut boy from {img}, Luna's little brother: light-chestnut hair tuft sticking out of the top of his "
       "helmet, mint accents, mint knee pads, mint chest button. Leo is slightly shorter than Luna.")
STELLINA = ("- STELLINA = the glowing star from {img}: soft pastel-yellow five-pointed star with very rounded points, translucent "
            "bioluminescent body glowing from inside with tiny yellow, mint and pink light specks and a soft glow halo, big glossy "
            "brown eyes, pink cheeks. NO arms, NO legs. She is always floating and moves only by floating, wiggling, spinning and glowing.")
CAST_HEAD = "CAST (keep every design detail identical to the reference sheets: face, proportions, hair, suit colors and stripes, helmet):"

SETS = {
 "mars_A": "use {img} as the background: Mars with orange dunes, the white rocket cut by the left edge, bright blue starry sky in the upper part. Do not change the set.",
 "mars_B": "use {img} as the background: open Mars landscape with soft orange dunes, a small crater on the right, round red rocks, bright blue starry sky with the little Earth in the upper right. Do not change the set.",
 "mars_C": "use {img} as the background: Mars with the small white-and-orange rover on the left edge, a shallow crater and round red rocks on the right, bright blue starry sky with a ringed planet. Do not change the set.",
}
REFS = {"luna": "characters/luna_sheet_CANON.png", "leo": "characters/leo_sheet_CANON.png",
        "leo_no_helmet": "characters/leo_no_helmet_sheet.png", "space_friends": "props/space_friends_sheet.png",
        "leo_gear": "props/leo_gear_sheet.png", "color_stones_baskets": "props/color_stones_baskets_sheet.png",
        "stellina": "characters/stella_sheet_CANON.png",
        "mars_A": "worlds/mars_A_CANON.png", "mars_B": "worlds/mars_B_CANON.png", "mars_C": "worlds/mars_C_CANON.png"}

# Regole di crescita (13/10/2026, da YouTube Analytics/assistente): aggancio immediato + loop perfetto
HOOK_LOOP = ("HOOK: from the very first frame the characters are already visible and moving, with bright colors: no fade-in, no empty "
             "scene, no slow intro. LOOP: the last second ends with the characters in the SAME positions, poses, facial expressions, framing and lighting as "
             "the very first frame, so that the end flows seamlessly back into the beginning. ")

RULES_BASE = ("helmets always on, children's feet on the ground, consistent faces and colors in every frame, smooth bouncy "
              "toddler-friendly motion, no morphing, no flicker, no text, no numbers, no letters, no logos.")
AUDIO_TAIL = " No song titles, no lyrics, no words, no speech, no loud sounds, no sudden noises."

EPISODES = {
 "EP002": dict(
  title="Condividiamo la merenda", slug="condividiamo_la_merenda", duration=15, cast=["luna", "leo", "stellina"], world="mars_B",
  props=["space_friends"],
  props_text="- THE THREE LITTLE SPACE FRIENDS are exactly those of {space_friends}: a lilac moon bunny with long floppy ears, a round white robot that rolls on ONE wheel with mint lights and a mint antenna ball, and a chubby green alien with big brown eyes and a little glowing antenna. Keep their designs identical to the sheet.",
  goal="Buone maniere: condividere. Struttura 'uno alla volta' (Lalafun, 2,31 Mld): tre amici, tre biscotti, premio finale.",
  action=[
   "0-2s: Luna and Leo stand side by side in the center. STELLINA floats down next to Luna and glows on Luna's small white backpack; Luna takes out three big star-shaped cookies and Leo claps.",
   "2-5s: the lilac moon bunny hops out of the crater on the right; STELLINA leaves a soft sparkle trail towards it; Luna gives it one cookie; the bunny hugs the cookie, does a happy hop and hops back into the crater.",
   "5-8s: the round white robot rolls out of the crater on its one wheel; Leo gives it one cookie; the robot spins happily with blinking lights and rolls back into the crater.",
   "8-11s: the chubby green alien peeks out of the crater; Luna gives it the last cookie; it does a happy twirl.",
   "11-13s: Luna and Leo look into the empty backpack and at each other with a small surprised shrug; the bunny, the robot and the little alien peek out of the crater together and toss small cookie pieces to them.",
   "13-15s: Luna and Leo munch happily and wave at the camera, standing in the center like at 0s; STELLINA glows brighter between them.",
  ],
  rules="RULES: Luna, Leo and STELLINA are always visible. The little friends appear ONE at a time and go back into the crater; only at 11-15s the three little friends peek out together. The little friends are small (knee height of the children), cute and never scary. ",
  audio="AUDIO: an original cheerful marimba and ukulele melody for toddlers, 100 bpm; a soft 'pop' when each friend appears, a tiny happy squeak for the bunny, a cute 'bip-bip' for the robot, a giggle for the little alien, soft 'nom nom' munching at 13-15s, three soft bell chimes when STELLINA glows.",
  title_it="Luna e Leo condividono la merenda 🍪 | Buone maniere per bambini #shorts",
  title_en="Luna & Leo Share Their Snack 🍪 | Good Manners for Kids #shorts",
 ),
 "EP003": dict(
  title="Uno, due, tre stelline!", slug="uno_due_tre_stelline", duration=15, cast=["luna", "leo", "stellina"], world="mars_A",
  goal="Contare 1-2-3. Struttura NuNu Tv (5,53 Mld): una cosa alla volta. Stellina fa spuntare dalla sabbia tre stelline di cristallo, una alla volta da sinistra a destra; i bambini corrono verso ognuna, la indicano e fanno un salto grande (niente conteggio con le dita: i modelli video sbagliano il numero di dita). Numeri 1-2-3 aggiunti in post sopra ogni stellina.",
  camera=CAM_FIXED,
  framing=("FRAMING: medium shot, the SAME framing from the very first frame to the last. Luna and Leo are BIG: their full bodies fill "
           "about half of the frame height, their feet at about 25% from the bottom edge. The lower quarter of the frame is the sand in front "
           "of them, where the three crystal stars pop up in a row (left, center, right). STELLINA floats just above the children's helmets."),
  action=[
   "0-2s: Luna and Leo, already big in the frame, stand side by side on the left near the rocket; STELLINA floats just above them and does a happy spin.",
   "2-5s: STELLINA floats to the LEFT part of the sand and taps the ground: ONE big golden crystal star (as tall as the children's knees, plain, with NO face) pops up out of the sand with a sparkle. Luna and Leo run over to it, point at it with both arms and do one BIG happy jump together, high off the ground, knees up.",
   "5-8s: STELLINA floats to the CENTER and taps the ground: a SECOND golden crystal star pops up in the center. The children run over to it, point at it and do a BIG happy jump together, high off the ground.",
   "8-11s: STELLINA floats to the RIGHT and taps the ground: a THIRD golden crystal star pops up on the right. The children run over, point at it and do the BIGGEST jump of all, arms up high; Leo lands with a little wobble and giggles.",
   "11-13s: the three crystal stars stand in a row on the sand (left, center, right) and glow together; STELLINA glows very brightly; Luna and Leo clap.",
   "13-15s: Luna and Leo wave at the camera standing next to the three crystal stars, STELLINA glowing above them.",
  ],
  rules="RULES: always exactly three characters: Luna, Leo and STELLINA, and only ONE STELLINA, who always stays close to the children at helmet height. The children count by pointing at each crystal star and jumping, NOT with their fingers: no finger counting. Jumps are big, bouncy and clearly visible, landing softly. The three crystal stars are objects, NOT characters: plain golden crystals shaped like stars, WITHOUT eyes, WITHOUT faces, standing on the sand in a horizontal row, each appearing only once and staying in place. Exactly three crystal stars at the end. ",
  audio="AUDIO: an original bouncy counting melody on glockenspiel and soft piano, 104 bpm; one bright rising note and a sparkly 'pop' each time a crystal star pops up (three notes going up), a big springy 'boing' on each jump, children's giggles at 8-11s, three soft bell chimes when STELLINA glows.",
  title_it="Contiamo fino a 3 con Stellina! ⭐⭐⭐ | Numeri per bambini #shorts",
  title_en="Count to 3 with Stella! ⭐⭐⭐ | Numbers for Toddlers #shorts",
  overlay=[["1", 3.0, 15.1, {"y": 0.705, "x": [[3, 0.3], [3.5, 0.3], [5, 0.27], [6, 0.23], [7, 0.23], [9, 0.18], [10, 0.17], [14, 0.17]]}], ["2", 6.0, 15.1, {"y": 0.705, "x": [[6, 0.57], [7, 0.53], [9, 0.5], [14, 0.5]]}], ["3", 9.0, 15.1, {"y": 0.705, "x": [[9, 0.83], [10, 0.82], [14, 0.8]]}]],  # numeri che seguono le stelline di cristallo (take 04)
 ),
 "EP004": dict(
  title="Segui Stellina!", slug="segui_stellina", duration=12, cast=["luna", "leo", "stellina"], world="mars_C",
  goal="Presentare i tre segnali di Stellina (scia = seguitemi, giravolta = fate come me, luce forte = bravi!). I bambini la seguono davvero e la camera li accompagna.",
  camera=("the framing is already medium and close from the very first frame, the children BIG. When STELLINA leads them to the right, "
          "the camera follows them with a smooth, slow sideways pan (tracking), keeping them big and centered; then it holds still. "
          "No zoom in or out, no fast moves, no shaking."),
  framing=("FRAMING: medium shot for the whole video. Luna and Leo are BIG: their full bodies fill about half of the frame height, "
           "feet at about 10% from the bottom edge. STELLINA floats just above and in front of them at helmet height."),
  action=[
   "0-2s: Luna and Leo stand side by side in the center, already big in the frame; STELLINA appears in front of them with a sparkle and does a happy spin.",
   "2-5s: STELLINA floats slowly to the right leaving a long trail of sparkles; Luna and Leo follow her with big happy bouncy hops across the red sand, and the camera follows them.",
   "5-8s: STELLINA stops and spins around in place; Luna and Leo stop and spin around with her, arms open.",
   "8-10s: STELLINA glows very brightly with happy closed eyes; Luna and Leo jump high and clap.",
   "10-12s: all three wave at the camera, Luna and Leo side by side in the center of the frame.",
  ],
  rules="RULES: always exactly three characters: Luna, Leo and STELLINA, and only ONE STELLINA, always close to the children. All fully visible. Keep the Mars set consistent while the camera follows them (orange sand, round red rocks, blue starry sky); the rover may slide out of the frame on the left. ",
  audio="AUDIO: an original gentle music-box and soft piano melody, 96 bpm, magical and sweet; a sparkly shimmer as STELLINA leaves her trail, soft 'boing' on each hop, a whoosh when they spin, three soft bell chimes when STELLINA glows brightly, a happy clap.",
  title_it="Segui Stellina! ⭐ | Cartoni per bambini piccoli #shorts",
  title_en="Follow the Twinkle! ⭐ Meet Stella | Shorts for Toddlers #shorts",
 ),
 "EP005": dict(
  title="Vestiamoci da astronauti", slug="vestiamoci_da_astronauti", duration=15, cast=["luna", "leo", "stellina"], world="mars_A",
  props=["leo_no_helmet", "leo_gear"],
  framing=("FRAMING: medium shot, the SAME framing from the very first frame to the last (no zoom, no push-in). Leo is BIG in the center: "
           "his full body fills about half of the frame height, feet at about 12% from the bottom edge; the small white box with his gear "
           "stands right next to him at knee height, fully visible. STELLINA floats just above the box at helmet height."),
  props_text="- LEO AT THE START looks exactly like {leo_no_helmet}: same jumpsuit, NO helmet, NO gloves, NO backpack, bare hands, light-chestnut hair with the tuft visible. Once fully dressed he looks exactly like {leo_img}.\n- LEO'S GEAR on the small white box is exactly that of {leo_gear}: round white helmet open at the front with a thin clear visor on the top edge, mint ear discs and an opening on top for his hair tuft; white gloves with mint fingertips and navy cuffs; a plain white rounded backpack with no straps.",
  goal="Routine: vestirsi in ordine, un pezzo alla volta (struttura 'Get dressed').",
  action=[
   "0-2s: Leo stands in the center in his astronaut jumpsuit but WITHOUT helmet, gloves and backpack, his light-chestnut hair visible; next to him on the small white box lie his gloves, his backpack and his helmet. STELLINA floats over and glows on the gloves.",
   "2-5s: Leo puts on the white gloves with mint fingertips, then claps his hands happily.",
   "5-8s: STELLINA glows on the backpack; Leo puts the small white backpack on his back and does a little hop.",
   "8-11s: STELLINA glows on the helmet; Leo puts on his round white helmet, his hair tuft pops out of the top, and he does a proud astronaut pose with fists on his hips.",
   "11-13s: Luna, already fully dressed in her suit and helmet, walks in from the left edge of the frame and gives Leo a high five.",
   "13-15s: Luna and Leo wave at the camera side by side in the center; STELLINA glows brightly between them.",
  ],
  rules="RULES: Leo and STELLINA always visible, Luna enters only at 11s. Leo's suit, gloves, backpack and helmet are exactly those of his reference sheet. Each item is put on smoothly and stays on. ",
  audio="AUDIO: an original playful 'getting ready' melody on ukulele and xylophone, 104 bpm; a soft 'click' each time an item is put on, a clap sound at 2-5s, a happy 'ta-da' chord at 8-11s, a 'clap' on the high five, three soft bell chimes when STELLINA glows.",
  title_it="Vestiamoci da astronauti! 🧑‍🚀 | Routine per bambini #shorts",
  title_en="Let's Get Dressed for Space! 🧑‍🚀 | Getting Dressed for Toddlers #shorts",
 ),
 "EP006": dict(
  title="Sassi colorati", slug="sassi_colorati", duration=15, cast=["luna", "leo", "stellina"], world="mars_B",
  props=["color_stones_baskets"],
  framing=("FRAMING: medium shot, the SAME framing from the very first frame to the last (no zoom, no push-in). Luna and Leo are BIG in the "
           "center: their full bodies fill about half of the frame height, feet at about 25% from the bottom edge. In the lower quarter of the "
           "frame, in front of them on the sand, stand the three baskets in a row (red on the left, blue in the center, yellow on the right), "
           "with the three stones lying next to them. Everything is fully visible. STELLINA floats just above the children's helmets."),
  props_text="- THE STONES AND BASKETS are exactly those of {color_stones_baskets}: one smooth shiny RED stone, one BLUE stone, one YELLOW stone, and three woven baskets in the same red, blue and yellow, each basket about knee height of the children.",
  goal="Colori: rosso, blu, giallo; smistare (struttura Emily's Playhouse, 3,04 Mld).",
  action=[
   "0-2s: Luna and Leo stand in the center; in front of them on the sand lie the three shiny stones (RED, BLUE, YELLOW) and the three baskets in the same colors. STELLINA floats over the stones and makes them sparkle.",
   "2-5s: Luna picks up the RED stone and puts it into the RED basket; the red basket glows red.",
   "5-8s: Leo picks up the BLUE stone and puts it into the BLUE basket; the blue basket glows blue.",
   "8-11s: Leo picks up the YELLOW stone and puts it into the YELLOW basket on the right; the yellow basket glows yellow; Luna claps and they giggle.",
   "11-13s: all three baskets glow with their colors; STELLINA glows very brightly above them; Luna and Leo do a BIG happy jump, arms up high.",
   "13-15s: Luna and Leo wave at the camera, standing in the center like at 0s.",
  ],
  rules="RULES: always exactly three characters: Luna, Leo and STELLINA. Exactly three stones and three baskets, colors never change. Each child holds only ONE stone at a time and puts it into the basket of the SAME color: Luna touches ONLY the red stone and the red basket; Leo touches ONLY the blue stone and then the yellow stone. A stone never goes into a basket of a different color, never jumps or changes color, and once in its basket it stays there. ",
  audio="AUDIO: an original cheerful xylophone and marimba melody, 100 bpm; a different bright 'ding' for each color (low for red, middle for blue, high for yellow), giggles at 8-11s, three soft bell chimes when STELLINA glows.",
  title_it="Sassi colorati su Marte! 🔴🔵🟡 | I colori per bambini #shorts",
  title_en="Sort the Space Rocks by Color! 🔴🔵🟡 | Colors for Toddlers #shorts",
 ),
 "EP007": dict(
  title="Fai come Stellina!", slug="fai_come_stellina", duration=15, cast=["luna", "leo", "stellina"], world="mars_C",
  goal="Imitare movimenti (struttura Monica Toy 'Imitoys', 3,63 Mld): tre round, il terzo buffo.",
  framing=("FRAMING: wide-medium shot, the SAME framing from the very first frame to the last (no zoom, no push-in). Luna stands on the LEFT and "
           "Leo on the RIGHT, side by side near the center; their full bodies fill about one third of the frame height, feet at about 20% from the "
           "bottom edge; the white-and-orange rover is on the left edge, red rocks behind them, the ringed planet in the upper right sky. STELLINA "
           "floats above them in the middle of the sky, always visible."),
  action=[
   "0-2s: Luna and Leo stand side by side in the center-right; STELLINA floats in front of them at helmet height and does a little hop in the air.",
   "2-5s: STELLINA bounces up and down twice, and at every bounce she flashes with a bright burst of warm golden light and sparkles; Luna and Leo copy her with two BIG jumps, high off the ground.",
   "5-8s: STELLINA spins slowly once; Luna and Leo copy her: each turns around ONE single full turn to the SAME side (both turn to their own right: first we see their right side, then their back, then their left side, then their face again), a smooth continuous turn that takes the whole 3 seconds, arms open. The head turns together with the body: the face never flips to the other side.",
   "8-11s: STELLINA floats up high; Luna and Leo stretch their arms up and stand on tiptoes; Leo stretches too much, wobbles and sits down on his bottom, giggling.",
   "11-13s: Luna helps Leo stand up, both laugh; STELLINA comes back down and glows brightly.",
   "13-15s: Luna and Leo wave at the camera, standing in the center-right like at 0s.",
  ],
  rules="RULES: always exactly three characters: Luna, Leo and STELLINA. The rover stays still in the background. Leo's fall is soft and funny, never painful. Every turn is smooth and continuous in one direction only: no snapping, no reversing direction, no sudden jumps in rotation. STELLINA glows brightly every time she bounces. ",
  audio="AUDIO: an original playful 'copy me' melody on ukulele and glockenspiel, 108 bpm; a 'boing' for the jumps, a whoosh for the spin, a rising slide-whistle when they stretch, a soft cartoon 'plop' when Leo sits down, children's laughter at 11-13s, three soft bell chimes when STELLINA glows.",
  title_it="Fai come Stellina! ⭐ | Balliamo e muoviamoci #shorts",
  title_en="Copy Stella! ⭐ Move & Dance for Toddlers #shorts",
 ),
 "EP008": dict(
  title="Ciao, sono Luna!", slug="ciao_sono_luna", duration=12, cast=["luna", "stellina"], world="mars_A",
  goal="Presentazione di Luna (formato 'Ciao!'): tre gesti che la rendono riconoscibile.",
  framing=("FRAMING: medium shot, the SAME framing from the very first frame to the last (no zoom, no push-in). Luna is BIG: her full body "
           "fills about half of the frame height, feet at about 12% from the bottom edge; the white rocket is cut by the left edge. "
           "STELLINA, when she arrives, floats next to Luna at helmet height."),
  action=[
   "0-2s: Luna, already big in the frame, peeks out from behind the rocket on the left edge, then hops to the center and smiles at the camera.",
   "2-5s: Luna waves hello, then does ONE slow graceful twirl, turning in one single direction only (to her right) and ending facing the camera again.",
   "5-8s: Luna tilts her head left and right so her two hair buns with coral ties bounce, and giggles.",
   "8-10s: STELLINA floats in from above with a sparkle trail and glows brightly next to Luna; Luna gives her a gentle hug.",
   "10-12s: Luna waves at the camera in the center, STELLINA glowing next to her.",
  ],
  rules="RULES: only Luna until 8s, then exactly two characters: Luna and STELLINA, only ONE STELLINA. Luna's twirl is a smooth continuous turn in one direction: the head turns with the body, no snapping, no reversing, the face never flips. Luna always wears her one-piece jumpsuit and helmet, NO skirt. ",
  audio="AUDIO: an original sweet ukulele and glockenspiel melody, 100 bpm; a soft chime on the twirl, giggles at 5-8s, three soft bell chimes when STELLINA arrives.",
  title_it="Ciao, sono Luna! 👧🚀 | Cartoni per bambini #shorts",
  title_en="Hi, I'm Luna! 👧🚀 | Meet Luna #shorts",
 ),
 "EP010": dict(
  title="Che colore viene?", slug="che_colore_viene", duration=15, cast=["luna", "leo", "stellina"], world="mars_A",
  goal="Mescolare i colori (struttura BiBiLo 'What Happens When Colors Mix?', 2,18 Mld): tre miscele una alla volta, con 'ooh!' a ogni nuovo colore.",
  framing=("FRAMING: medium shot, the SAME framing from the very first frame to the last (no zoom, no push-in). Luna stands on the LEFT and "
           "Leo on the RIGHT, facing each other a little, near the center; their full bodies fill about half of the frame height, feet at about "
           "20% from the bottom edge. STELLINA floats between and just above their helmets. The light balls are held in front of their chests."),
  action=[
   "0-2s: Luna and Leo stand on the left and right; STELLINA does a happy spin between them and, with a sparkle, a BIG glowing RED ball of light appears in Luna's hands and a BIG glowing YELLOW ball of light appears in Leo's hands; each ball is as big as a beach ball, soft and see-through like a glowing bubble.",
   "2-5s: Luna and Leo walk one step towards each other and gently touch the two balls together: RED and YELLOW melt into ONE big ORANGE glowing ball, the same orange as the Mars dunes; Luna and Leo open their mouths in a big surprised 'ooh!'; the orange ball floats up and stays above Luna's head on the left.",
   "5-8s: with a sparkle from STELLINA, a new BLUE ball appears in Luna's hands and a new YELLOW ball in Leo's hands; they touch them together and they melt into ONE big GREEN glowing ball; 'ooh!'; the green ball floats up and stays in the middle above STELLINA.",
   "8-11s: with a sparkle from STELLINA, a new RED ball appears in Luna's hands and a new BLUE ball in Leo's hands; they touch them together and they melt into ONE big PURPLE glowing ball; Leo giggles and wobbles; the purple ball floats up and stays above Leo's head on the right.",
   "11-13s: the ORANGE, GREEN and PURPLE balls glow together in a row in the upper part of the frame; STELLINA glows very brightly in the middle; Luna and Leo clap and do a happy jump.",
   "13-15s: Luna and Leo wave at the camera from the same spots as at 0s, STELLINA glowing between them.",
  ],
  rules="RULES: always exactly three characters: Luna, Leo and STELLINA, only ONE STELLINA; STELLINA never splits, never changes color and never has arms. Luna always holds the ball on the LEFT and Leo the ball on the RIGHT. Each mix uses exactly TWO balls that become exactly ONE ball of the new color; a ball never changes color by itself. The mixed balls are smooth glowing spheres with no faces. Luna and Leo always stay big and fully visible. ",
  audio="AUDIO: an original playful marimba and soft synth-bell melody, 100 bpm; a magic sparkle each time new balls appear, a soft bubbly 'bloop' and a rising glissando when two colors melt into one, children's 'ooh!' after each mix, giggles at 8-11s, three soft bell chimes when STELLINA glows.",
  title_it="Che colore viene? 🎨 Mescoliamo i colori con Stellina ⭐ | Colori per bambini #shorts",
  title_en="What Color Comes Next? 🎨 Mixing Colors with Stella ⭐ | Colors for Toddlers #shorts",
 ),
 "EP011": dict(
  title="Ciao, sono Leo!", slug="ciao_sono_leo", duration=12, cast=["leo", "stellina"], world="mars_C",
  goal="Presentazione di Leo (formato 'Ciao!'): tre gesti che lo rendono riconoscibile — super salto, ciuffo, razzo umano.",
  framing=("FRAMING: medium shot, the SAME framing from the very first frame to the last (no zoom, no push-in). Leo is BIG: his full body "
           "fills about half of the frame height, feet at about 12% from the bottom edge, near the center-right; the rover stays on the left edge. "
           "STELLINA, when she arrives, floats next to Leo at helmet height."),
  action=[
   "0-2s: Leo, already big in the frame, pops up from behind a round red rock on the right with a happy face, then hops to the center-right and grins at the camera.",
   "2-5s: Leo waves hello, crouches down and does one SUPER JUMP high into the air with arms up, landing with a funny little wobble.",
   "5-8s: Leo points up at the light-chestnut hair tuft sticking out of the top of his helmet and wiggles his head so the tuft bounces, giggling.",
   "8-10s: Leo pretends to be a rocket: arms straight up, he rumbles and does a little 'blast-off' hop; STELLINA zooms in from above with a sparkle trail and glows brightly next to him.",
   "10-12s: Leo gives STELLINA a gentle hug, then waves at the camera with her glowing next to him.",
  ],
  rules="RULES: only Leo until 8s, then exactly two characters: Leo and STELLINA, only ONE STELLINA. Leo always wears his helmet with the hair tuft sticking out of the top, gloves and backpack exactly as in his sheet. All movements are smooth and continuous: no snapping, no reversing. ",
  audio="AUDIO: an original playful ukulele and xylophone melody, 108 bpm; a springy 'boing' on the super jump, a funny wobble sound on the landing, giggles at 5-8s, a playful rocket rumble and 'whoosh' at 8-10s, three soft bell chimes when STELLINA arrives.",
  title_it="Ciao, sono Leo! 👦🚀 | Cartoni per bambini #shorts",
  title_en="Hi, I'm Leo! 👦🚀 | Meet Leo #shorts",
 ),
 "EP026": dict(
  title="Prendi la bolla!", slug="prendi_la_bolla", duration=12, cast=["luna", "leo", "stellina"], world="mars_A",
  goal="Colori rosso, blu, giallo (playlist colori). Interattivo: il bambino dice il colore prima che la bolla venga presa. Loop perfetto, niente saluto finale.",
  framing=("FRAMING: medium shot, the SAME framing from the very first frame to the last (no zoom, no push-in). Luna stands on the LEFT and "
           "Leo on the RIGHT, side by side in the center; their full bodies fill about 40% of the frame height, feet at about 18% from the bottom "
           "edge. STELLINA floats in the middle, just above their helmets. The upper part of the frame is open blue starry sky where the bubbles come down."),
  action=[
   "0-1s: Luna and Leo already stand in their spots looking up; a BIG glowing RED bubble of light (as big as a beach ball, soft and see-through) is already floating down from the sky above Luna, released by STELLINA with a sparkle.",
   "1-4s: the RED bubble slowly lands in Luna's open arms; Luna catches it and it bursts softly into a shower of red sparkles; Luna giggles and gives a little hop, then stands again in her spot looking up.",
   "4-7s: STELLINA sends a BIG glowing BLUE bubble down above Leo; it slowly lands in Leo's open arms and bursts into blue sparkles; Leo does a happy wiggle, then stands again in his spot looking up.",
   "7-10s: STELLINA sends a BIG glowing YELLOW bubble down between them; Luna and Leo catch it TOGETHER with their hands and it bursts into golden sparkles all around them; both do a small happy jump.",
   "10-12s: Luna and Leo land and stand still in their starting spots looking up, exactly as at the very beginning, while a new BIG RED bubble starts floating down from the sky above Luna.",
  ],
  rules="RULES: always exactly three characters: Luna, Leo and STELLINA, only ONE STELLINA; STELLINA never changes color, never splits and never has arms. Only ONE bubble at a time. Luna catches ONLY the red bubble, Leo catches ONLY the blue bubble, the yellow one is caught by both together. The bubbles are smooth glowing spheres with no faces, each keeps its color until it bursts. Luna and Leo always stay big and fully visible and never wave at the camera. ",
  audio="AUDIO: an original playful marimba and glockenspiel melody, 100 bpm; a soft rising 'whoo' while each bubble floats down, a gentle bubbly 'pop' and a sparkle when it bursts (a different bright note for red, blue and yellow), children's giggles; the music ends on the same note and phrase it starts with, so the video loops seamlessly.",
  title_it="Prendi la bolla! 🔴🔵🟡 Impariamo i colori con Stellina ⭐ | Colori per bambini #shorts",
  title_en="Catch the Bubble! 🔴🔵🟡 Learn Colors with Stella ⭐ | Colors for Toddlers #shorts",
  desc_it="Prendi la bolla! Stellina fa scendere dal cielo di Marte tante bolle colorate: Luna prende la rossa, Leo la blu e insieme prendono la gialla! Di che colore è la prossima? 🔴🔵🟡 ⭐",
  desc_en="Catch the bubble! Stella sends colorful bubbles down from the sky of Mars: Luna catches the red one, Leo the blue one and together they catch the yellow one! What color comes next? 🔴🔵🟡 ⭐",
  cover_s=8.4,
 ),
 "EP025": dict(
  title="Ciao, sono Stellina!", slug="ciao_sono_stellina", duration=12, cast=["luna", "leo", "stellina"], world="mars_B",
  goal="Presentazione di Stellina (formato 'Ciao!'): i suoi tre poteri — luce che respira, scia di scintille, giravolta — poi arrivano Luna e Leo.",
  framing=("FRAMING: medium shot, the SAME framing from the very first frame to the last (no zoom, no push-in). STELLINA is the star of the "
           "shot: she floats in the center of the frame, BIG, about one quarter of the frame width. When Luna and Leo arrive they stand below "
           "her, full body, about one third of the frame height, feet at about 12% from the bottom edge."),
  action=[
   "0-2s: a tiny twinkle in the blue sky grows brighter and brighter and becomes STELLINA, who pops out in the center with a happy smile and a burst of sparkles.",
   "2-5s: STELLINA shows her light: she glows softly, then very brightly, then softly again, three gentle pulses like breathing, with happy closed eyes on the brightest one.",
   "5-8s: STELLINA flies a small loop in the air leaving a long trail of golden and pastel sparkles that slowly fades.",
   "8-10s: STELLINA does one slow happy spin in place, always the same direction; Luna and Leo run in from the left and right edges, smiling.",
   "10-12s: Luna and Leo stand below STELLINA and wave at the camera together with her, STELLINA glowing brightly.",
  ],
  rules="RULES: only STELLINA until 8s, then exactly three characters: STELLINA, Luna and Leo, only ONE STELLINA. STELLINA never has arms or legs. Smooth continuous motion, no snapping. ",
  audio="AUDIO: an original magical music-box and harp melody, 92 bpm, sweet and calm; a rising shimmer at 0-2s, three soft bell chimes when STELLINA appears, soft 'whoom' glows on each light pulse, a sparkly whoosh on the loop, light children's giggles when Luna and Leo arrive.",
  title_it="Ciao, sono Stellina! ⭐ | Cartoni per bambini #shorts",
  title_en="Hi, I'm Stella! ⭐ | Meet Stella #shorts",
 ),
}


def build(ep_id):
    E = EPISODES[ep_id]
    order = E["cast"] + E.get("props", []) + [E["world"]]
    tag = {k: f"@Image{i+1}" for i, k in enumerate(order)}
    cast_lines = [CAST_HEAD] + [{"luna": LUNA, "leo": LEO, "stellina": STELLINA}[c].format(img=tag[c]) for c in E["cast"]]
    if E.get("props_text"):
        t = E["props_text"].replace("{leo_img}", tag.get("leo", ""))
        for k in E.get("props", []): t = t.replace("{" + k + "}", tag[k])
        cast_lines.append(t)
    framing = E.get("framing") or (FRAMING_SOLO.format(who=E["framing_solo"][0], obj=E["framing_solo"][1]) if "framing_solo" in E else FRAMING)
    sections = [
        ("HEADER", HEADER(E["duration"], E.get("camera"))),
        ("FRAMING", framing),
        ("STYLE", STYLE),
        ("CAST", "\n".join(cast_lines)),
        ("SET", "SET: " + SETS[E["world"]].format(img=tag[E["world"]])),
        ("ACTION", "ACTION (gentle, bouncy movements in time with the music):\n" + "\n".join(E["action"])),
        ("RULES", E["rules"] + ("" if E.get("no_loop") else HOOK_LOOP) + RULES_BASE),
        ("AUDIO", E["audio"] + AUDIO_TAIL),
    ]
    refs = [(tag[k], "mondo" if k == E["world"] else ("prop" if k in E.get("props", []) else "personaggio"), k, REFS[k]) for k in order]
    return E, sections, refs
