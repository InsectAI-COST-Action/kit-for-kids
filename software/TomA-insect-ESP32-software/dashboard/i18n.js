// Small, dependency-free i18n layer shared by dashboard.html and demo.html.
//
// Design notes (see docs/next-session.md for the full plan this implements):
// - `LOCALES` is a registry, not a hardcoded pair - every picker in the app
//   (this dashboard, demo.html, the phone control app) reads from a list like
//   this one, so adding a language later is one new entry, not new UI logic.
// - Composed/pluralized strings (counts, durations) are functions, not plain
//   strings, so each language's own grammar lives in its own function body
//   rather than one shared pluralization rule bent to fit every language.
// - `t(key, ...args)` falls back to English, then to the raw key, so a
//   missing translation degrades to something visible and debuggable rather
//   than a blank UI.
(() => {
  const LOCALES = [
    { code: 'en', label: 'English', flag: '\u{1F1EC}\u{1F1E7}' },
    { code: 'es', label: 'Español', flag: '\u{1F1EA}\u{1F1F8}' },
  ];

  const STORAGE_KEY = 'insectai-locale';
  const DEFAULT_LOCALE = 'en';

  const pluralEn = (n, singular, plural) => (n === 1 ? singular : (plural ?? `${singular}s`));
  const pluralEs = (n, singular, plural) => (n === 1 ? singular : plural);

  const translations = {
    en: {
      'locale.pickerLabel': 'Language',

      'loading.eyebrow': 'Your camera adventure',
      'loading.title': 'Opening your camera adventure…',
      'loading.message': 'Finding your pictures on the card.',
      'loading.detail': 'Getting everything ready',
      'loadingError.title': 'We could not open these pictures',
      'loadingError.message': 'Try checking that the camera card is connected, then try again.',
      'loadingError.retry': 'Try again',

      'hero.eyebrow': 'Insect AI Kit-for-Kids',
      'hero.title': 'What did your camera see?',
      'hero.statusDefault': 'Getting your pictures ready…',

      'welcome.eyebrow': 'Ready to explore',
      'welcome.titlePrefix': 'Your camera took',
      'welcome.titleSuffix': 'pictures!',
      'welcome.body': 'Pick a picture, zoom in, and see what you can discover.',
      'welcome.cta': 'Explore pictures',

      'metrics.pictures.label': 'Pictures',
      'metrics.pictures.note': 'saved by your camera',
      'metrics.duration.label': 'Last adventure',
      'metrics.duration.note': 'how long your camera ran',
      'metrics.resolution.label': 'Picture size',
      'metrics.resolution.note': 'how big each picture is',
      'metrics.totalRecorded.label': 'Total time recorded',
      'metrics.totalRecorded.note': 'all your sessions added up',

      'cardCheck.eyebrow': 'Picture check',
      'cardCheck.title': 'Is everything still on the card?',
      'cardCheck.note': 'These counts come from the camera’s own record. If pictures were tidied off the card afterwards, the numbers above can be too high.',
      'cardCheck.button': 'Check the card',

      'explore.eyebrow': 'Look closely',
      'explore.title': 'Explore your pictures',
      'explore.body': 'Look closely at the world your camera watched.',
      'explore.cta': 'Show me the pictures',

      'ai.eyebrow': 'Your AI adventure',
      'ai.title': 'Ask the AI to look',
      'ai.body': 'Ask your computer to look through the pictures. It will share possible-insect clues, and AI can make mistakes.',
      'ai.cta': 'Find insects with AI',
      'ai.note': 'Choose the AI helper when you are ready. Your pictures stay on this computer.',

      'movie.eyebrow': 'Make a movie',
      'movie.title': 'Turn pictures into a tiny movie',
      'movie.body': 'Make a speedy time-lapse of everything your camera saw.',
      'movie.cta': 'Make my insect movie',
      'movie.note': 'It is made on this computer and downloaded when it is ready.',

      'settingsCard.eyebrow': 'Grown-up helper',
      'settingsCard.title': 'Set up your camera',
      'settingsCard.body': 'Choose a safe picture setting for your camera’s next adventure.',
      'settingsCard.cta': 'Camera settings',
      'settingsCard.note': 'Only change settings while the camera is switched off.',

      'motion.eyebrow': 'Motion watch',
      'motion.title': 'When did something move?',
      'motion.count': (n) => `${n} picture${n === 1 ? '' : 's'} saved`,
      'motion.hint': 'Your camera only kept a picture when its view changed enough. Each dot is one check — the orange dots crossed the line and got saved.',
      'motion.legend.saved': 'Picture saved',
      'motion.legend.quiet': 'Nothing moved',
      'motion.legend.threshold': 'Save line',

      'gallery.eyebrow': 'Picture time',
      'gallery.title': 'Your picture gallery',
      'gallery.count': (n) => `${n} picture${n === 1 ? '' : 's'}`,
      'gallery.empty': 'No committed images are available yet.',
      'gallery.showAll': 'Show all images',
      'gallery.showFewer': 'Show fewer images',

      'adult.summary': 'Adult details and frame search',
      'adult.filterTitle': 'Find frames',
      'adult.searchLabel': 'Search capture ID or outcome',
      'adult.searchPlaceholder': 'For example: completed',
      'adult.hint': 'Times are relative to the start of each session. This pilot has no calendar clock.',
      'adult.recentTitle': 'Recent committed frames',
      'adult.table.capture': 'Capture',
      'adult.table.time': 'Session time',
      'adult.table.outcome': 'Outcome',
      'adult.table.image': 'Image',
      'adult.showAllFrames': 'Show all frames',
      'adult.showFewerFrames': 'Show fewer frames',

      'modal.closeImage': 'Close image',
      'modal.closeMessage': 'Close message',
      'modal.closeMovie': 'Close movie maker',
      'modal.closeSettings': 'Close camera settings',
      'modal.closeAnalysis': 'Close AI adventure',
      'modal.close': 'x',

      'modelModal.title': 'The AI is still getting ready',
      'modelModal.body': 'We are building the picture-spotting part of this adventure. For now, you can explore every picture yourself.',
      'modelModal.ok': 'Keep exploring',

      'movieModal.eyebrow': 'Movie maker',
      'movieModal.title': 'Make your insect movie!',
      'movieModal.infoDefault': 'Getting your pictures ready for a time-lapse.',
      'movieModal.note': 'This makes an MP4 video from your saved pictures at 60 pictures per second. Nothing is uploaded or changed on the camera card.',
      'movieModal.cardStatusDefault': 'Press Load camera card, then choose the INSECT-AI drive in the next window.',
      'movieModal.startButton': 'Make movie',

      'movieProgress.eyebrow': 'Lights, camera, insects!',
      'movieProgress.title': 'Making your movie',
      'movieProgress.messageDefault': 'Getting the first picture ready.',
      'movieProgress.cancel': 'Cancel movie',
      'movieProgress.download': 'Download movie',

      'session.chooseLabel': 'Choose a session',
      'card.loadButton': 'Load camera card',
      'progress.text': (current, total) => `Picture ${current} of ${total}`,

      'settingsModal.intro': 'Choose a safe setting for the next camera adventure. The camera must be switched off while you change its card.',
      'settingsModal.currentDefault': 'Current setting: checking the camera card.',
      'settingsModal.legend': 'Choose your camera settings',
      'settingsModal.intervalLabel': 'How often should the camera take a picture?',
      'settingsModal.interval.sec1': '1 image every 1 second',
      'settingsModal.interval.sec2': '1 image every 2 seconds',
      'settingsModal.interval.sec30': '1 image every 30 seconds',
      'settingsModal.interval.min1': '1 image every 1 minute',
      'settingsModal.qualityLabel': 'How clear should the pictures be?',
      'settingsModal.quality.high': 'High quality',
      'settingsModal.quality.low': 'Low quality',
      'settingsModal.durationLabel': 'How long should the camera keep going?',
      'settingsModal.duration.min1': '1 minute',
      'settingsModal.duration.min5': '5 minutes',
      'settingsModal.duration.min30': '30 minutes',
      'settingsModal.duration.hour1': '1 hour',
      'settingsModal.duration.infinite': 'Infinite - until switched off',
      'settingsModal.motion.label': 'Save pictures only when something moves',
      'settingsModal.motion.hint': 'Experimental. The camera waits 5 seconds, always saves its first picture, then checks for a change before saving later pictures.',
      'settingsModal.allowCard': 'Allow camera-card changes',
      'settingsModal.save': 'Save this setting',
      'settingsModal.statusDefault': 'Choose the camera card to get started.',
      'settingsModal.safetyPrefix': 'Saving replaces only',
      'settingsModal.safetySuffix': '. It takes effect after the board is restarted.',

      'analysisModal.eyebrow': 'AI adventure',
      'analysisModal.title': 'Let’s look for possible insects!',
      'analysisModal.intro': 'Choose the top camera-card folder once. The AI helper will look at your pictures one at a time, and its clues can be wrong.',
      'analysisModal.legend': 'How should the AI look at this session?',
      'analysisModal.antaiTest.label': 'AntAI – Test \u{1F9EA}',
      'analysisModal.antaiTest.hint': 'Experimental ant helper — not yet checked for accuracy. It checks each whole picture once.',
      'analysisModal.flatbugQuick.label': 'FlatBug – Quick look \u{1F680}',
      'analysisModal.flatbugQuick.hint': 'Fast general insect helper — checks each whole picture once. Best for bigger, clearer insects.',
      'analysisModal.flatbugClose.label': 'FlatBug – Look closely \u{1F50E}',
      'analysisModal.flatbugClose.hint': 'Slower general insect helper — checks 12 zoomed-in pieces. Better for tiny insects.',
      'analysisModal.sessionNoteDefault': 'Choose the newest available session to begin.',
      'analysisModal.cardStatusDefault': 'Press Load camera card, then choose the INSECT-AI drive in the next window. The browser can read the pictures and AI helper, but never change them.',
      'analysisModal.startButton': 'Start looking',

      'analysisScanner.eyebrow': 'AI detective at work',
      'analysisScanner.title': 'Looking through your pictures',
      'analysisScanner.storyDefault': 'Getting ready to look carefully…',
      'analysisScanner.canvasLabel': 'The picture currently being checked',
      'analysisScanner.captionDefault': 'Waiting for the first picture',
      'analysisScanner.pause': 'Pause search',
      'analysisScanner.resume': 'Resume search',
      'analysisScanner.stop': 'Stop search',

      'discoveries.eyebrow': 'Live discoveries',
      'discoveries.title': 'Clues found so far',
      'discoveries.count': (n) => `${n} possible insect${n === 1 ? '' : 's'} found`,
      'discoveries.empty': 'No clues yet — the AI is still looking carefully.',

      'cardPicker.ariaLabel': 'Choose camera card folder',

      'movie.pictureUnavailable': 'Picture unavailable',
      'movie.pressLoadFirst': 'Press Load camera card first.',
      'movie.noSavedFiles': 'There are no saved picture files to make into a movie yet.',
      'movie.needsModernBrowser': 'Movie making needs current Chrome or Edge with its local video tools enabled.',
      'movie.startingMessage': 'Starting a properly timed MP4 movie.',
      'movie.finishing': 'Finishing your MP4 movie...',
      'movie.addingPicture': (n) => `Adding picture ${n} to your speedy insect story.`,
      'movie.cancelledMessage': 'Movie cancelled. No file was made.',
      'movie.readyMessage': 'Your 60 pictures-per-second MP4 insect movie is ready! Download it to keep it.',
      'movie.failedMessage': 'We could not make this movie on this computer. Try current Chrome or Edge, then try again.',
      'movie.detailPrefix': (message) => `Movie maker detail: ${message}`,
      'session.optionLabel': (runId, count, isNewest) => `${isNewest ? 'Newest session - ' : ''}${runId} (${count} pictures)`,
      'movie.infoSelected': (label, duration) => `${label} is selected. At 60 pictures each second, your movie will be about ${duration} long.`,
      'movie.infoEmpty': 'There are no saved pictures to turn into a movie yet.',
      'movie.cardReady': (totalFiles, sessionsLength, missing) => `Camera card ready! I found ${totalFiles} saved picture${totalFiles === 1 ? '' : 's'} in ${sessionsLength} session${sessionsLength === 1 ? '' : 's'}.${missing ? ` ${missing} older record${missing === 1 ? '' : 's'} without image files will be skipped.` : ''}`,
      'time.seconds': (n) => `${n} seconds`,
      'cardCheck.tryAnotherFolder': 'Try another folder',
      'cardCheck.mismatchDrift': (present, referenced, missing) => `Checked the card: ${present} of ${referenced} pictures are still here. ${missing} picture${missing === 1 ? ' is' : 's are'} in the camera's record but no longer on the card, so ${missing === 1 ? 'it is' : 'they are'} not counted above. Nothing on the card was changed.`,
      'cardCheck.allPresent': (present) => `Checked the card: all ${present} picture${present === 1 ? '' : 's'} in the camera's record ${present === 1 ? 'is' : 'are'} still here.`,
      'cardCheck.wrongFolder': 'That folder does not hold any of this card’s pictures. Choose the top camera-card folder - the one holding dashboard.html - and try again.',
      'hero.readyStatus': (n) => `Ready! Your camera saved ${n} picture${n === 1 ? '' : 's'}.`,
      'hero.noPicturesYet': 'No pictures are on this card yet. Try another camera card or run.',
      'table.unknownCapture': 'Unknown capture',
      'table.unknownOutcome': 'Unknown',
      'table.openImage': 'Open image',
      'table.noLongerOnCard': 'No longer on the card',
      'table.unavailable': 'Unavailable',
      'table.frameCaption': (id) => `Frame ${id}`,
      'gallery.noSearchMatch': 'No pictures match that search.',
      'ai.noAIYet': 'Your camera does not run AI on its own, but you can ask this computer to look for possible insects any time - choose an AI helper below.',
      'ai.hasResults': 'This card already has AI results saved on it, ready to explore.',
      'pageTitle.cameraAdventure': (n) => `Camera adventure - ${n} pictures`,
      'loading.readingCurrent': 'Reading the current session',
      'loading.foundNewest': 'Found the newest pictures',
      'loading.checkingGroups': 'Checking saved picture groups',
      'loading.puttingInOrder': 'Putting your pictures in order.',
      'loading.groupProgress': (current, total) => `Picture group ${current} of ${total}`,
      'loading.someGroupsFailed': (n) => `Some picture groups could not be opened (${n}). The pictures that loaded are still available.`,
      'loading.needsHelp': 'Your pictures need a little help to open.',
      'loading.noGroupsReadable': 'No picture groups could be read from this card.',
      'motion.saveLine': (threshold) => `save line (${threshold})`,
      'motion.dotTitle': (id, isSaved, score) => `${id || 'capture'}: ${isSaved ? 'saved' : 'not saved'}, score ${score}`,
      'motion.baselineTitle': (id) => `${id || 'first picture'}: always kept as a starting point`,

      'analysis.noSessionSelected': 'No session selected',
      'analysis.sessionSelected': (label) => `${label} is selected. The AI will only look at these pictures.`,
      'analysis.noSessionsAvailable': 'There are no saved picture sessions available on this card.',
      'analysis.antaiTestNote': 'AntAI - Test is selected: an experimental ant helper with no accuracy check yet, so treat its clues with extra caution.',
      'analysis.flatbugQuickNote': 'FlatBug Quick look is selected: one fast check of each whole picture.',
      'analysis.flatbugCloseNote': 'FlatBug Look closely is selected: 12 zoomed-in checks for each picture, so it takes longer.',
      'analysis.possibleInsectLabel': (percent) => `${percent}% possible insect`,
      'analysis.pictureCaption': (id) => `Picture ${id}`,
      'analysis.possibleInsectHeading': 'A possible insect!',
      'analysis.discoveryDetail': (id, n, percent) => `${id} - ${n} possible insect${n === 1 ? '' : 's'} - strongest clue ${percent}%`,
      'analysis.summaryText': (inspected, discoveries, errors) => `${inspected} picture${inspected === 1 ? '' : 's'} checked. ${discoveries} possible insect${discoveries === 1 ? '' : 's'} found.${errors ? ` ${errors} picture${errors === 1 ? '' : 's'} could not be checked.` : ''} These are experimental predictions and AI can make mistakes.`,
      'analysis.metricPossible': (n) => `${n} possible`,
      'analysis.metricChecked': 'Checked',
      'analysis.lookingAtPiece': (id, current, total) => `Looking at ${id} - piece ${current} of ${total}`,
      'analysis.thinkingMessages': ['Looking carefully...', 'Searching the shapes...', 'Checking for tiny wings and legs...', 'Being a brilliant bug detective...'],
      'analysis.allDone': 'That is every picture. What a careful search!',
      'analysis.pausedMessage': 'Paused. Your discoveries are safe on this page.',
      'analysis.noPicturesAtAll': 'There are no saved pictures for the AI to look at yet.',
      'analysis.noAvailableFiles': 'There are no saved picture files available for the AI to look at yet.',
      'analysis.wakingUp': 'Waking up the AI helper...',
      'analysis.metricLooking': 'Looking...',
      'analysis.lookingAtAvailable': (n, m) => `Looking at ${n} available pictures. ${m} older record${m === 1 ? '' : 's'} without image files will be skipped.`,
      'analysis.modeCloseMessage': 'Looking closely in 12 picture pieces for tiny possible insects...',
      'analysis.modeQuickMessage': 'Taking a quick look through each whole picture...',
      'analysis.modelReady': (modelName, label, count, missing) => `${modelName} is ready! ${label} has ${count} saved picture${count === 1 ? '' : 's'}.${missing ? ` ${missing} older record${missing === 1 ? '' : 's'} without image files will be skipped.` : ''} Press Start looking.`,
      'analysis.cardReadyWithSession': (label, count) => `Camera card ready! ${label} has ${count} saved picture${count === 1 ? '' : 's'}. Press Start looking.`,
      'analysis.missingHelper': (name, list) => `Your pictures are ready, but this card has no ${name} helper in ai/: ${list}. Add the AI pack to the card, then try again.`,
      'analysis.openingModel': (name) => `Opening ${name} and waking up the AI helper...`,
      'analysis.readingModel': (name) => `Reading the ${name} helper from the card...`,
      'analysis.startingModel': (name) => `Starting ${name}...`,
      'analysis.couldNotStart': (message) => `The AI helper could not start: ${message}`,
      'analysis.noSavedPicturesInFolder': 'This folder has no saved camera pictures in it. Choose the top camera-card folder and try again.',
      'analysis.noFolderChosen': 'No folder was chosen. Press Load camera card to try again.',
      'analysis.cardReadyBackground': 'Camera card ready. The AI helper starts when you open this.',
      'analysis.keepLooking': 'Keep looking',
      'analysis.finishingThenPausing': 'Finishing this picture, then pausing...',
      'analysis.searchStopped': 'Search stopped. You can start a new search whenever you like.',
      'analysis.cardStatusShort': 'Press Load camera card, then choose the INSECT-AI drive in the next window.',

      'settings.quality.highLabel': 'High quality (QXGA)',
      'settings.quality.lowLabel': 'Low quality (VGA)',
      'settings.intervalPhrase': (seconds) => (seconds === 60 ? 'one picture every 1 minute' : `one picture every ${seconds} second${seconds === 1 ? '' : 's'}`),
      'settings.durationPhrase': (seconds) => {
        if (seconds === 0) return 'until you switch the camera off';
        const minutes = seconds / 60;
        return `${minutes} minute${minutes === 1 ? '' : 's'}`;
      },
      'settings.unknownWord': 'unknown',
      'settings.unknownQuality': (frameSize, jpegQuality) => `${frameSize || 'unknown'} quality ${jpegQuality ?? 'unknown'}`,
      'settings.motionOnDescription': 'save the first picture, then only save changes (motion score 5)',
      'settings.motionOffDescription': 'save every picture',
      'settings.describeComposed': (interval, image, duration, motion) => `${interval}, ${image}, for ${duration}; ${motion}`,
      'settings.cardReadyChoose': 'Camera card ready. Choose your three settings, then save them to the card.',
      'settings.browserCannotWrite': 'This browser cannot safely change camera-card files. Use current Chrome or Edge for this experimental tool.',
      'settings.pleaseAllowAgain': 'Your pictures are loaded. To change settings, choose the same camera-card folder once more and allow changes.',
      'settings.chooseAndAllow': 'Choose the top INSECT-AI camera-card folder and allow changes.',
      'settings.currentMatches': (desc) => `Current setting on this card: ${desc}. The choices below match it.`,
      'settings.currentNoMatch': (desc) => `Current setting on this card: ${desc}. Choose one of the safe settings below to replace it.`,
      'settings.currentUnavailable': 'Current setting: not available until the camera card is chosen.',
      'settings.chooseAndAllowBrowserPrompt': 'Choose the top INSECT-AI camera-card folder, then allow changes when your browser asks.',
      'settings.cardNotChanged': (message) => `The camera card was not changed: ${message}`,
      'settings.infiniteWarning': '\n\nInfinite means the camera keeps taking pictures until it is switched off or the card fills up.',
      'settings.confirmPrompt': (description, extraWarning) => `Save this camera setting?\n\n${description}${extraWarning}\n\nIt will replace config.json and take effect after the board is restarted.`,
      'settings.saving': 'Saving the camera setting safely...',
      'settings.savedMessage': (desc) => `Saved! The next camera session will use ${desc}. Safely disconnect the card, then restart the board.`,
      'settings.currentSaved': (desc) => `Current setting on this card: ${desc}. Saved to config.json; the choices above now match it.`,

      'card.chooseFolderPrompt': 'Choose the top camera-card folder in the window your browser just opened.',
      'card.cannotAskPermission': 'This browser cannot ask for permission to change a folder.',
      'card.permissionNotGranted': 'Permission to change this camera card was not granted.',
      'card.fileNotFound': (name) => `${name} was not found on the selected camera card.`,
      'card.onlyRootFilenameRead': 'Only a card-root filename may be read.',
      'card.onlyRootFilenameWrite': 'Only a card-root filename may be changed.',
      'card.chooseAndAllowFirst': 'Choose the camera card and allow changes first.',
      'card.readingProgress': (done, total) => `Reading the camera card: ${done} of ${total} files.`,
      'card.ready': 'Camera card ready.',
      'card.emptyFolder': 'That folder had no files in it.',

      'demo.cardStatusDefault': 'This demo is already loaded — no folder to choose.',
      'demo.settingsIntroPrefix': 'Choose a safe setting for the next camera adventure. This demo folder has its own practice',
      'demo.settingsIntroSuffix': '— a real camera card is never touched.',
      'demo.settingsSafetyPrefix': 'Saving replaces only this demo folder’s',
      'demo.settingsSafetySuffix': '. It takes effect after a real board is restarted with matching settings.',
      'demo.analysisCardStatusDefault': 'This demo is already loaded — no folder to choose. The browser can read the pictures and AI helper, but never change them.',
    },
    es: {
      'locale.pickerLabel': 'Idioma',

      'loading.eyebrow': 'Tu aventura con la cámara',
      'loading.title': 'Abriendo tu aventura con la cámara…',
      'loading.message': 'Buscando tus fotos en la tarjeta.',
      'loading.detail': 'Preparando todo',
      'loadingError.title': 'No hemos podido abrir estas fotos',
      'loadingError.message': 'Comprueba que la tarjeta de la cámara esté conectada, y vuelve a intentarlo.',
      'loadingError.retry': 'Volver a intentarlo',

      'hero.eyebrow': 'Insect AI Kit-for-Kids',
      'hero.title': '¿Qué ha visto tu cámara?',
      'hero.statusDefault': 'Preparando tus fotos…',

      'welcome.eyebrow': 'Listos para explorar',
      'welcome.titlePrefix': 'Tu cámara ha hecho',
      'welcome.titleSuffix': '¡fotos!',
      'welcome.body': 'Elige una foto, acerócate y descubre qué puedes encontrar.',
      'welcome.cta': 'Explorar fotos',

      'metrics.pictures.label': 'Fotos',
      'metrics.pictures.note': 'guardadas por tu cámara',
      'metrics.duration.label': 'Última aventura',
      'metrics.duration.note': 'cuánto tiempo estuvo funcionando tu cámara',
      'metrics.resolution.label': 'Tamaño de la foto',
      'metrics.resolution.note': 'lo grande que es cada foto',
      'metrics.totalRecorded.label': 'Tiempo total grabado',
      'metrics.totalRecorded.note': 'sumando todas tus sesiones',

      'cardCheck.eyebrow': 'Comprobación de fotos',
      'cardCheck.title': '¿Sigue todo en la tarjeta?',
      'cardCheck.note': 'Estos números vienen del propio registro de la cámara. Si se borraron fotos de la tarjeta después, los números de arriba pueden ser demasiado altos.',
      'cardCheck.button': 'Comprobar la tarjeta',

      'explore.eyebrow': 'Mira de cerca',
      'explore.title': 'Explora tus fotos',
      'explore.body': 'Mira de cerca el mundo que ha visto tu cámara.',
      'explore.cta': 'Ver las fotos',

      'ai.eyebrow': 'Tu aventura con la IA',
      'ai.title': 'Pide a la IA que mire',
      'ai.body': 'Pide a tu ordenador que revise las fotos. Compartirá pistas de posibles insectos, y la IA puede equivocarse.',
      'ai.cta': 'Buscar insectos con IA',
      'ai.note': 'Elige el ayudante de IA cuando estés listo. Tus fotos se quedan en este ordenador.',

      'movie.eyebrow': 'Haz una peli',
      'movie.title': 'Convierte tus fotos en una pequeña peli',
      'movie.body': 'Haz un time-lapse rápido con todo lo que vio tu cámara.',
      'movie.cta': 'Hacer mi peli de insectos',
      'movie.note': 'Se hace en este ordenador y se descarga cuando esté lista.',

      'settingsCard.eyebrow': 'Ayudante para mayores',
      'settingsCard.title': 'Configura tu cámara',
      'settingsCard.body': 'Elige un ajuste seguro para la próxima aventura de tu cámara.',
      'settingsCard.cta': 'Ajustes de la cámara',
      'settingsCard.note': 'Cambia los ajustes solo mientras la cámara está apagada.',

      'motion.eyebrow': 'Vigilancia de movimiento',
      'motion.title': '¿Cuándo se movió algo?',
      'motion.count': (n) => `${n} foto${n === 1 ? '' : 's'} guardada${n === 1 ? '' : 's'}`,
      'motion.hint': 'Tu cámara solo guardó una foto cuando la imagen cambió lo suficiente. Cada punto es una comprobación — los puntos naranjas superaron la línea y se guardaron.',
      'motion.legend.saved': 'Foto guardada',
      'motion.legend.quiet': 'Nada se movió',
      'motion.legend.threshold': 'Línea de guardado',

      'gallery.eyebrow': 'Hora de las fotos',
      'gallery.title': 'Tu galería de fotos',
      'gallery.count': (n) => `${n} foto${n === 1 ? '' : 's'}`,
      'gallery.empty': 'Todavía no hay imágenes guardadas disponibles.',
      'gallery.showAll': 'Ver todas las fotos',
      'gallery.showFewer': 'Ver menos fotos',

      'adult.summary': 'Detalles para adultos y búsqueda de fotogramas',
      'adult.filterTitle': 'Buscar fotogramas',
      'adult.searchLabel': 'Buscar por ID de captura o resultado',
      'adult.searchPlaceholder': 'Por ejemplo: completed',
      'adult.hint': 'Los tiempos son relativos al inicio de cada sesión. Este piloto no tiene reloj de calendario.',
      'adult.recentTitle': 'Fotogramas guardados recientes',
      'adult.table.capture': 'Captura',
      'adult.table.time': 'Tiempo de sesión',
      'adult.table.outcome': 'Resultado',
      'adult.table.image': 'Imagen',
      'adult.showAllFrames': 'Ver todos los fotogramas',
      'adult.showFewerFrames': 'Ver menos fotogramas',

      'modal.closeImage': 'Cerrar imagen',
      'modal.closeMessage': 'Cerrar mensaje',
      'modal.closeMovie': 'Cerrar creador de películas',
      'modal.closeSettings': 'Cerrar ajustes de la cámara',
      'modal.closeAnalysis': 'Cerrar aventura de IA',
      'modal.close': 'x',

      'modelModal.title': 'La IA todavía se está preparando',
      'modelModal.body': 'Estamos construyendo la parte de búsqueda de fotos de esta aventura. Por ahora, puedes explorar cada foto tú mismo.',
      'modelModal.ok': 'Seguir explorando',

      'movieModal.eyebrow': 'Creador de películas',
      'movieModal.title': '¡Haz tu peli de insectos!',
      'movieModal.infoDefault': 'Preparando tus fotos para un time-lapse.',
      'movieModal.note': 'Esto crea un vídeo MP4 con tus fotos guardadas a 60 fotos por segundo. No se sube ni se cambia nada en la tarjeta de la cámara.',
      'movieModal.cardStatusDefault': 'Pulsa Cargar tarjeta de la cámara, y elige la unidad INSECT-AI en la siguiente ventana.',
      'movieModal.startButton': 'Hacer la peli',

      'movieProgress.eyebrow': '¡Luces, cámara, insectos!',
      'movieProgress.title': 'Haciendo tu peli',
      'movieProgress.messageDefault': 'Preparando la primera foto.',
      'movieProgress.cancel': 'Cancelar la peli',
      'movieProgress.download': 'Descargar la peli',

      'session.chooseLabel': 'Elige una sesión',
      'card.loadButton': 'Cargar tarjeta de la cámara',
      'progress.text': (current, total) => `Foto ${current} de ${total}`,

      'settingsModal.intro': 'Elige un ajuste seguro para la próxima aventura de la cámara. La cámara debe estar apagada mientras cambias su tarjeta.',
      'settingsModal.currentDefault': 'Ajuste actual: comprobando la tarjeta de la cámara.',
      'settingsModal.legend': 'Elige los ajustes de tu cámara',
      'settingsModal.intervalLabel': '¿Con qué frecuencia debe hacer una foto la cámara?',
      'settingsModal.interval.sec1': '1 foto cada 1 segundo',
      'settingsModal.interval.sec2': '1 foto cada 2 segundos',
      'settingsModal.interval.sec30': '1 foto cada 30 segundos',
      'settingsModal.interval.min1': '1 foto cada 1 minuto',
      'settingsModal.qualityLabel': '¿Con qué claridad deben verse las fotos?',
      'settingsModal.quality.high': 'Calidad alta',
      'settingsModal.quality.low': 'Calidad baja',
      'settingsModal.durationLabel': '¿Durante cuánto tiempo debe seguir la cámara?',
      'settingsModal.duration.min1': '1 minuto',
      'settingsModal.duration.min5': '5 minutos',
      'settingsModal.duration.min30': '30 minutos',
      'settingsModal.duration.hour1': '1 hora',
      'settingsModal.duration.infinite': 'Infinito - hasta que se apague',
      'settingsModal.motion.label': 'Guardar fotos solo cuando algo se mueve',
      'settingsModal.motion.hint': 'Experimental. La cámara espera 5 segundos, siempre guarda su primera foto, y después comprueba si hay cambios antes de guardar las siguientes.',
      'settingsModal.allowCard': 'Permitir cambios en la tarjeta',
      'settingsModal.save': 'Guardar este ajuste',
      'settingsModal.statusDefault': 'Elige la tarjeta de la cámara para empezar.',
      'settingsModal.safetyPrefix': 'Al guardar solo se reemplaza',
      'settingsModal.safetySuffix': '. Se aplica después de reiniciar la placa.',

      'analysisModal.eyebrow': 'Aventura con la IA',
      'analysisModal.title': '¡Busquemos posibles insectos!',
      'analysisModal.intro': 'Elige la carpeta principal de la tarjeta una vez. El ayudante de IA mirará tus fotos una a una, y sus pistas pueden estar equivocadas.',
      'analysisModal.legend': '¿Cómo debe mirar la IA esta sesión?',
      'analysisModal.antaiTest.label': 'AntAI – Test \u{1F9EA}',
      'analysisModal.antaiTest.hint': 'Ayudante experimental de hormigas — todavía no se ha comprobado su precisión. Revisa cada foto completa una vez.',
      'analysisModal.flatbugQuick.label': 'FlatBug – Vistazo rápido \u{1F680}',
      'analysisModal.flatbugQuick.hint': 'Ayudante rápido de insectos en general — revisa cada foto completa una vez. Mejor para insectos grandes y claros.',
      'analysisModal.flatbugClose.label': 'FlatBug – Mirar de cerca \u{1F50E}',
      'analysisModal.flatbugClose.hint': 'Ayudante más lento de insectos en general — revisa 12 trozos ampliados. Mejor para insectos pequeños.',
      'analysisModal.sessionNoteDefault': 'Elige la sesión más reciente disponible para empezar.',
      'analysisModal.cardStatusDefault': 'Pulsa Cargar tarjeta de la cámara, y elige la unidad INSECT-AI en la siguiente ventana. El navegador puede leer las fotos y el ayudante de IA, pero nunca los cambia.',
      'analysisModal.startButton': 'Empezar a buscar',

      'analysisScanner.eyebrow': 'La IA detective trabajando',
      'analysisScanner.title': 'Revisando tus fotos',
      'analysisScanner.storyDefault': 'Preparándose para mirar con cuidado…',
      'analysisScanner.canvasLabel': 'La foto que se está revisando ahora',
      'analysisScanner.captionDefault': 'Esperando la primera foto',
      'analysisScanner.pause': 'Pausar la búsqueda',
      'analysisScanner.resume': 'Reanudar la búsqueda',
      'analysisScanner.stop': 'Detener la búsqueda',

      'discoveries.eyebrow': 'Descubrimientos en directo',
      'discoveries.title': 'Pistas encontradas hasta ahora',
      'discoveries.count': (n) => `${n} posible${n === 1 ? '' : 's'} insecto${n === 1 ? '' : 's'} encontrado${n === 1 ? '' : 's'}`,
      'discoveries.empty': 'Aún no hay pistas — la IA sigue mirando con cuidado.',

      'cardPicker.ariaLabel': 'Elige la carpeta de la tarjeta de la cámara',

      'movie.pictureUnavailable': 'Foto no disponible',
      'movie.pressLoadFirst': 'Primero pulsa Cargar tarjeta de la cámara.',
      'movie.noSavedFiles': 'Todavía no hay archivos de fotos guardados para hacer una película.',
      'movie.needsModernBrowser': 'Para hacer la película hace falta Chrome o Edge actualizado, con sus herramientas de vídeo locales activadas.',
      'movie.startingMessage': 'Empezando una película MP4 bien sincronizada.',
      'movie.finishing': 'Terminando tu película MP4…',
      'movie.addingPicture': (n) => `Añadiendo la foto ${n} a tu historia rápida de insectos.`,
      'movie.cancelledMessage': 'Película cancelada. No se ha creado ningún archivo.',
      'movie.readyMessage': '¡Tu película MP4 de insectos a 60 fotos por segundo está lista! Descárgala para guardarla.',
      'movie.failedMessage': 'No hemos podido hacer esta película en este ordenador. Prueba con Chrome o Edge actualizado, y vuelve a intentarlo.',
      'movie.detailPrefix': (message) => `Detalle del creador de películas: ${message}`,
      'session.optionLabel': (runId, count, isNewest) => `${isNewest ? 'Sesión más reciente - ' : ''}${runId} (${count} fotos)`,
      'movie.infoSelected': (label, duration) => `${label} está seleccionada. A 60 fotos por segundo, tu película durará unos ${duration}.`,
      'movie.infoEmpty': 'Todavía no hay fotos guardadas para convertir en película.',
      'movie.cardReady': (totalFiles, sessionsLength, missing) => `¡Tarjeta de la cámara lista! He encontrado ${totalFiles} foto${totalFiles === 1 ? '' : 's'} guardada${totalFiles === 1 ? '' : 's'} en ${sessionsLength} sesión${sessionsLength === 1 ? '' : 'es'}.${missing ? ` ${missing} registro${missing === 1 ? '' : 's'} antiguo${missing === 1 ? '' : 's'} sin archivo de imagen se omitirá${missing === 1 ? '' : 'n'}.` : ''}`,
      'time.seconds': (n) => `${n} segundos`,
      'cardCheck.tryAnotherFolder': 'Probar otra carpeta',
      'cardCheck.mismatchDrift': (present, referenced, missing) => `Tarjeta comprobada: ${present} de ${referenced} fotos siguen aquí. ${missing} foto${missing === 1 ? '' : 's'} está${missing === 1 ? '' : 'n'} en el registro de la cámara pero ya no en la tarjeta, así que no se cuenta${missing === 1 ? '' : 'n'} arriba. No se ha cambiado nada en la tarjeta.`,
      'cardCheck.allPresent': (present) => `Tarjeta comprobada: las ${present} foto${present === 1 ? '' : 's'} del registro de la cámara sigue${present === 1 ? '' : 'n'} aquí.`,
      'cardCheck.wrongFolder': 'Esa carpeta no tiene ninguna de las fotos de esta tarjeta. Elige la carpeta principal de la tarjeta de la cámara — la que tiene dashboard.html — y vuelve a intentarlo.',
      'hero.readyStatus': (n) => `¡Listo! Tu cámara ha guardado ${n} foto${n === 1 ? '' : 's'}.`,
      'hero.noPicturesYet': 'Todavía no hay fotos en esta tarjeta. Prueba con otra tarjeta de cámara u otra sesión.',
      'table.unknownCapture': 'Captura desconocida',
      'table.unknownOutcome': 'Desconocido',
      'table.openImage': 'Abrir imagen',
      'table.noLongerOnCard': 'Ya no está en la tarjeta',
      'table.unavailable': 'No disponible',
      'table.frameCaption': (id) => `Fotograma ${id}`,
      'gallery.noSearchMatch': 'Ninguna foto coincide con esa búsqueda.',
      'ai.noAIYet': 'Tu cámara no usa IA por sí sola, pero puedes pedirle a este ordenador que busque posibles insectos cuando quieras — elige un ayudante de IA abajo.',
      'ai.hasResults': 'Esta tarjeta ya tiene resultados de IA guardados, listos para explorar.',
      'pageTitle.cameraAdventure': (n) => `Aventura con la cámara - ${n} fotos`,
      'loading.readingCurrent': 'Leyendo la sesión actual',
      'loading.foundNewest': 'Encontradas las fotos más recientes',
      'loading.checkingGroups': 'Comprobando los grupos de fotos guardados',
      'loading.puttingInOrder': 'Ordenando tus fotos.',
      'loading.groupProgress': (current, total) => `Grupo de fotos ${current} de ${total}`,
      'loading.someGroupsFailed': (n) => `Algunos grupos de fotos no se han podido abrir (${n}). Las fotos que sí se cargaron siguen disponibles.`,
      'loading.needsHelp': 'Tus fotos necesitan un poco de ayuda para abrirse.',
      'loading.noGroupsReadable': 'No se ha podido leer ningún grupo de fotos de esta tarjeta.',
      'motion.saveLine': (threshold) => `línea de guardado (${threshold})`,
      'motion.dotTitle': (id, isSaved, score) => `${id || 'captura'}: ${isSaved ? 'guardada' : 'no guardada'}, puntuación ${score}`,
      'motion.baselineTitle': (id) => `${id || 'primera foto'}: siempre se guarda como punto de partida`,

      'analysis.noSessionSelected': 'Ninguna sesión seleccionada',
      'analysis.sessionSelected': (label) => `${label} está seleccionada. La IA solo mirará estas fotos.`,
      'analysis.noSessionsAvailable': 'No hay sesiones de fotos guardadas disponibles en esta tarjeta.',
      'analysis.antaiTestNote': 'AntAI - Test está seleccionado: un ayudante experimental de hormigas sin comprobación de precisión todavía, así que trata sus pistas con especial cautela.',
      'analysis.flatbugQuickNote': 'FlatBug Vistazo rápido está seleccionado: una comprobación rápida de cada foto completa.',
      'analysis.flatbugCloseNote': 'FlatBug Mirar de cerca está seleccionado: 12 comprobaciones ampliadas por foto, así que tarda más.',
      'analysis.possibleInsectLabel': (percent) => `${percent}% posible insecto`,
      'analysis.pictureCaption': (id) => `Foto ${id}`,
      'analysis.possibleInsectHeading': '¡Un posible insecto!',
      'analysis.discoveryDetail': (id, n, percent) => `${id} - ${n} posible${n === 1 ? '' : 's'} insecto${n === 1 ? '' : 's'} - pista más fuerte ${percent}%`,
      'analysis.summaryText': (inspected, discoveries, errors) => `${inspected} foto${inspected === 1 ? '' : 's'} revisada${inspected === 1 ? '' : 's'}. ${discoveries} posible${discoveries === 1 ? '' : 's'} insecto${discoveries === 1 ? '' : 's'} encontrado${discoveries === 1 ? '' : 's'}.${errors ? ` ${errors} foto${errors === 1 ? '' : 's'} no se pudo${errors === 1 ? '' : 'ieron'} revisar.` : ''} Son predicciones experimentales, y la IA puede equivocarse.`,
      'analysis.metricPossible': (n) => `${n} posible${n === 1 ? '' : 's'}`,
      'analysis.metricChecked': 'Revisado',
      'analysis.lookingAtPiece': (id, current, total) => `Mirando ${id} - trozo ${current} de ${total}`,
      'analysis.thinkingMessages': ['Mirando con cuidado…', 'Buscando las formas…', 'Comprobando pequeñas alas y patas…', 'Siendo un detective de bichos brillante…'],
      'analysis.allDone': '¡Esa era la última foto! Qué búsqueda tan cuidadosa.',
      'analysis.pausedMessage': 'En pausa. Tus descubrimientos están a salvo en esta página.',
      'analysis.noPicturesAtAll': 'Todavía no hay fotos guardadas para que la IA mire.',
      'analysis.noAvailableFiles': 'Todavía no hay archivos de fotos disponibles para que la IA mire.',
      'analysis.wakingUp': 'Despertando al ayudante de IA…',
      'analysis.metricLooking': 'Buscando…',
      'analysis.lookingAtAvailable': (n, m) => `Mirando ${n} fotos disponibles. ${m} registro${m === 1 ? '' : 's'} antiguo${m === 1 ? '' : 's'} sin archivo de imagen se omitirá${m === 1 ? '' : 'n'}.`,
      'analysis.modeCloseMessage': 'Mirando de cerca en 12 trozos de la foto en busca de insectos pequeños…',
      'analysis.modeQuickMessage': 'Echando un vistazo rápido a cada foto completa…',
      'analysis.modelReady': (modelName, label, count, missing) => `¡${modelName} está listo! ${label} tiene ${count} foto${count === 1 ? '' : 's'} guardada${count === 1 ? '' : 's'}.${missing ? ` ${missing} registro${missing === 1 ? '' : 's'} antiguo${missing === 1 ? '' : 's'} sin archivo de imagen se omitirá${missing === 1 ? '' : 'n'}.` : ''} Pulsa Empezar a buscar.`,
      'analysis.cardReadyWithSession': (label, count) => `¡Tarjeta de la cámara lista! ${label} tiene ${count} foto${count === 1 ? '' : 's'} guardada${count === 1 ? '' : 's'}. Pulsa Empezar a buscar.`,
      'analysis.missingHelper': (name, list) => `Tus fotos están listas, pero esta tarjeta no tiene el ayudante ${name} en ai/: ${list}. Añade el paquete de IA a la tarjeta y vuelve a intentarlo.`,
      'analysis.openingModel': (name) => `Abriendo ${name} y despertando al ayudante de IA…`,
      'analysis.readingModel': (name) => `Leyendo el ayudante ${name} desde la tarjeta…`,
      'analysis.startingModel': (name) => `Iniciando ${name}…`,
      'analysis.couldNotStart': (message) => `El ayudante de IA no se ha podido iniciar: ${message}`,
      'analysis.noSavedPicturesInFolder': 'Esta carpeta no tiene fotos de cámara guardadas. Elige la carpeta principal de la tarjeta de la cámara y vuelve a intentarlo.',
      'analysis.noFolderChosen': 'No se ha elegido ninguna carpeta. Pulsa Cargar tarjeta de la cámara para volver a intentarlo.',
      'analysis.cardReadyBackground': 'Tarjeta de la cámara lista. El ayudante de IA se inicia cuando abras esto.',
      'analysis.keepLooking': 'Seguir buscando',
      'analysis.finishingThenPausing': 'Terminando esta foto, y pausando…',
      'analysis.searchStopped': 'Búsqueda detenida. Puedes empezar una nueva búsqueda cuando quieras.',
      'analysis.cardStatusShort': 'Pulsa Cargar tarjeta de la cámara, y elige la unidad INSECT-AI en la siguiente ventana.',

      'settings.quality.highLabel': 'Calidad alta (QXGA)',
      'settings.quality.lowLabel': 'Calidad baja (VGA)',
      'settings.intervalPhrase': (seconds) => (seconds === 60 ? 'una foto cada 1 minuto' : `una foto cada ${seconds} segundo${seconds === 1 ? '' : 's'}`),
      'settings.durationPhrase': (seconds) => {
        if (seconds === 0) return 'hasta que apagues la cámara';
        const minutes = seconds / 60;
        return `${minutes} minuto${minutes === 1 ? '' : 's'}`;
      },
      'settings.unknownWord': 'desconocido',
      'settings.unknownQuality': (frameSize, jpegQuality) => `calidad ${frameSize || 'desconocida'} ${jpegQuality ?? 'desconocida'}`,
      'settings.motionOnDescription': 'guarda la primera foto, y después solo guarda cambios (puntuación de movimiento 5)',
      'settings.motionOffDescription': 'guarda todas las fotos',
      'settings.describeComposed': (interval, image, duration, motion) => `${interval}, ${image}, durante ${duration}; ${motion}`,
      'settings.cardReadyChoose': 'Tarjeta de la cámara lista. Elige tus tres ajustes y guárdalos en la tarjeta.',
      'settings.browserCannotWrite': 'Este navegador no puede cambiar de forma segura los archivos de la tarjeta de la cámara. Usa Chrome o Edge actualizado para esta herramienta experimental.',
      'settings.pleaseAllowAgain': 'Tus fotos están cargadas. Para cambiar los ajustes, elige otra vez la misma carpeta de la tarjeta de la cámara y permite los cambios.',
      'settings.chooseAndAllow': 'Elige la carpeta principal de la tarjeta INSECT-AI y permite los cambios.',
      'settings.currentMatches': (desc) => `Ajuste actual en esta tarjeta: ${desc}. Las opciones de abajo coinciden con él.`,
      'settings.currentNoMatch': (desc) => `Ajuste actual en esta tarjeta: ${desc}. Elige uno de los ajustes seguros de abajo para reemplazarlo.`,
      'settings.currentUnavailable': 'Ajuste actual: no disponible hasta que se elija la tarjeta de la cámara.',
      'settings.chooseAndAllowBrowserPrompt': 'Elige la carpeta principal de la tarjeta INSECT-AI, y después permite los cambios cuando tu navegador lo pregunte.',
      'settings.cardNotChanged': (message) => `No se ha cambiado la tarjeta de la cámara: ${message}`,
      'settings.infiniteWarning': '\n\nInfinito significa que la cámara sigue haciendo fotos hasta que se apague o la tarjeta se llene.',
      'settings.confirmPrompt': (description, extraWarning) => `¿Guardar este ajuste de la cámara?\n\n${description}${extraWarning}\n\nSe reemplazará config.json y se aplicará después de reiniciar la placa.`,
      'settings.saving': 'Guardando el ajuste de la cámara de forma segura…',
      'settings.savedMessage': (desc) => `¡Guardado! La próxima sesión de la cámara usará ${desc}. Desconecta la tarjeta de forma segura y después reinicia la placa.`,
      'settings.currentSaved': (desc) => `Ajuste actual en esta tarjeta: ${desc}. Guardado en config.json; las opciones de arriba ya coinciden con él.`,

      'card.chooseFolderPrompt': 'Elige la carpeta principal de la tarjeta de la cámara en la ventana que acaba de abrir tu navegador.',
      'card.cannotAskPermission': 'Este navegador no puede pedir permiso para cambiar una carpeta.',
      'card.permissionNotGranted': 'No se ha concedido permiso para cambiar esta tarjeta de la cámara.',
      'card.fileNotFound': (name) => `No se ha encontrado ${name} en la tarjeta de la cámara elegida.`,
      'card.onlyRootFilenameRead': 'Solo se puede leer un archivo de la raíz de la tarjeta.',
      'card.onlyRootFilenameWrite': 'Solo se puede cambiar un archivo de la raíz de la tarjeta.',
      'card.chooseAndAllowFirst': 'Primero elige la tarjeta de la cámara y permite los cambios.',
      'card.readingProgress': (done, total) => `Leyendo la tarjeta de la cámara: ${done} de ${total} archivos.`,
      'card.ready': 'Tarjeta de la cámara lista.',
      'card.emptyFolder': 'Esa carpeta no tenía archivos.',

      'demo.cardStatusDefault': 'Esta demostración ya está cargada — no hay que elegir ninguna carpeta.',
      'demo.settingsIntroPrefix': 'Elige un ajuste seguro para la próxima aventura de la cámara. Esta carpeta de demostración tiene su propio',
      'demo.settingsIntroSuffix': 'de práctica — nunca se toca una tarjeta de cámara real.',
      'demo.settingsSafetyPrefix': 'Al guardar solo se reemplaza el',
      'demo.settingsSafetySuffix': 'de esta carpeta de demostración. Se aplica después de reiniciar una placa real con los mismos ajustes.',
      'demo.analysisCardStatusDefault': 'Esta demostración ya está cargada — no hay que elegir ninguna carpeta. El navegador puede leer las fotos y el ayudante de IA, pero nunca los cambia.',
    },
  };

  let currentLocale = DEFAULT_LOCALE;
  try {
    const saved = window.localStorage ? localStorage.getItem(STORAGE_KEY) : null;
    if (saved && translations[saved]) currentLocale = saved;
  } catch (error) { /* private browsing / blocked storage: keep the default */ }

  const t = (key, ...args) => {
    const table = translations[currentLocale] || translations[DEFAULT_LOCALE];
    const entry = table[key] !== undefined ? table[key] : translations[DEFAULT_LOCALE][key];
    if (entry === undefined) return key;
    return typeof entry === 'function' ? entry(...args) : entry;
  };

  const getLocale = () => currentLocale;

  const listeners = new Set();
  const onLocaleChange = (fn) => listeners.add(fn);

  const applyStaticText = () => {
    document.documentElement.lang = currentLocale;
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      el.textContent = t(el.getAttribute('data-i18n'));
    });
    document.querySelectorAll('[data-i18n-attr]').forEach((el) => {
      el.getAttribute('data-i18n-attr').split(',').forEach((pair) => {
        const [attr, key] = pair.split(':');
        el.setAttribute(attr.trim(), t(key.trim()));
      });
    });
  };

  const setLocale = (code) => {
    if (!translations[code] || code === currentLocale) return;
    currentLocale = code;
    try { if (window.localStorage) localStorage.setItem(STORAGE_KEY, code); } catch (error) { /* ignore */ }
    applyStaticText();
    listeners.forEach((fn) => fn(code));
  };

  const buildLocalePicker = (container) => {
    if (!container) return null;
    const select = document.createElement('select');
    select.className = 'locale-picker';
    select.setAttribute('aria-label', t('locale.pickerLabel'));
    LOCALES.forEach(({ code, label, flag }) => {
      const option = document.createElement('option');
      option.value = code;
      option.textContent = `${flag} ${code.toUpperCase()}`;
      option.title = label;
      select.append(option);
    });
    select.value = currentLocale;
    select.addEventListener('change', () => setLocale(select.value));
    onLocaleChange(() => { select.value = currentLocale; select.setAttribute('aria-label', t('locale.pickerLabel')); });
    container.append(select);
    return select;
  };

  window.i18n = { LOCALES, t, getLocale, setLocale, onLocaleChange, applyStaticText, buildLocalePicker };

  document.addEventListener('DOMContentLoaded', () => {
    applyStaticText();
    buildLocalePicker(document.getElementById('locale-picker-slot'));
  });
})();
