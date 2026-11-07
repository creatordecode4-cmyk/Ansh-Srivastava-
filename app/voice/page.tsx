"use client";
// ↑ Ye line batati hai ki ye page browser me chalega (Client Component).
//   Mic aur Web Speech API sirf browser me milte hain, server pe nahi.

import { useEffect, useRef, useState } from "react";

/* ------------------------------------------------------------------
   1) TypeScript types
   TypeScript ki default library me SpeechRecognition ke types nahi hote,
   isliye hum sirf utne types khud likh rahe hain jitne humein chahiye.
------------------------------------------------------------------- */
type SpeechRecognitionAlternativeLike = { transcript: string };
type SpeechRecognitionResultLike = {
  isFinal: boolean; // true = ye hissa pakka ho gaya, false = abhi bol rahe ho (interim)
  0: SpeechRecognitionAlternativeLike;
};
type SpeechRecognitionEventLike = {
  resultIndex: number; // is event me naye results kis index se shuru hue
  results: ArrayLike<SpeechRecognitionResultLike>;
};
type SpeechRecognitionErrorEventLike = { error: string };

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: (() => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
};
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

// Chrome me ye "webkitSpeechRecognition" naam se milta hai, kuch browsers me "SpeechRecognition".
function getSpeechRecognition(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null; // server pe window nahi hota
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/* ------------------------------------------------------------------
   2) Error codes → simple Hindi message
------------------------------------------------------------------- */
const ERROR_MESSAGES: Record<string, string> = {
  "not-allowed":
    "माइक की अनुमति नहीं मिली। Address bar के पास 🔒 आइकन दबाकर Microphone को Allow करें, फिर दोबारा कोशिश करें।",
  "service-not-allowed":
    "Browser ने आवाज़ पहचानने की सेवा रोक दी है। Chrome में खोलें और पक्का करें कि साइट https:// पर चल रही है।",
  "no-speech": "कोई आवाज़ सुनाई नहीं दी। माइक के पास साफ़ बोलें और फिर से बटन दबाएँ।",
  "audio-capture": "माइक नहीं मिला। देखें कि माइक लगा है और कोई दूसरा ऐप उसे इस्तेमाल नहीं कर रहा।",
  network: "इंटरनेट की दिक्कत है। Chrome आवाज़ पहचानने के लिए इंटरनेट इस्तेमाल करता है, नेटवर्क चेक करें।",
  aborted: "सुनना बीच में रुक गया। फिर से बटन दबाएँ।",
  "language-not-supported": "यह भाषा इस browser में सपोर्ट नहीं है। दूसरी भाषा चुनकर देखें।",
  "bad-grammar": "आवाज़ पहचानने में अंदरूनी गड़बड़ हुई। फिर से कोशिश करें।",
};

function toHindiError(code: string): string {
  return ERROR_MESSAGES[code] ?? `कुछ गड़बड़ हो गई (कोड: ${code})। पेज रीफ़्रेश करके फिर कोशिश करें।`;
}

const LANGUAGES = [
  { code: "hi-IN", label: "हिंदी (hi-IN)" },
  { code: "en-IN", label: "English – India (en-IN)" },
];

/* ------------------------------------------------------------------
   3) Page component
------------------------------------------------------------------- */
export default function VoicePage() {
  // null = abhi check nahi kiya (server render), true/false = check ho gaya
  const [supported, setSupported] = useState<boolean | null>(null);
  const [listening, setListening] = useState(false);
  const [lang, setLang] = useState("hi-IN"); // default Hindi
  const [finalText, setFinalText] = useState(""); // pakka ho chuka text
  const [interimText, setInterimText] = useState(""); // abhi bolte waqt ka "live" text
  const [error, setError] = useState("");

  // useRef: value yaad rakhta hai par badalne pe page dobara render nahi karta.
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  // Page browser me khulte hi check karo ki API hai ya nahi.
  useEffect(() => {
    setSupported(getSpeechRecognition() !== null);

    // Cleanup: page chhodte waqt mic band kar do.
    return () => recognitionRef.current?.abort();
  }, []);

  function startListening() {
    const SpeechRecognition = getSpeechRecognition();
    if (!SpeechRecognition) {
      setSupported(false);
      return;
    }

    setError("");
    setInterimText("");

    const recognition = new SpeechRecognition();
    recognition.lang = lang; // kaun si bhasha sunni hai
    recognition.interimResults = true; // bolte waqt hi text dikhao
    // continuous = false: thoda chup hone pe apne aap ruk jaata hai.
    // Android Chrome pe ye zyada reliable hai (continuous mode me text repeat ho sakta hai).
    recognition.continuous = false;

    recognition.onstart = () => setListening(true);

    recognition.onresult = (event) => {
      let interim = "";
      let newFinal = "";
      // Sirf naye results (resultIndex se aage) padho.
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const text = result[0].transcript;
        if (result.isFinal) newFinal += text;
        else interim += text;
      }
      if (newFinal) {
        // Pakka text purane text ke aage jod do (beech me space).
        setFinalText((prev) => (prev ? `${prev} ${newFinal.trim()}` : newFinal.trim()));
      }
      setInterimText(interim);
    };

    recognition.onerror = (event) => {
      setError(toHindiError(event.error));
    };

    // Sunna khatam (khud ruka, error aaya ya stop dabaya) → button wapas chalu.
    recognition.onend = () => {
      setListening(false);
      setInterimText("");
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
      setListening(true); // turant button disable, taaki double-tap na ho
    } catch {
      setListening(false);
      setError("सुनना शुरू नहीं हो पाया। एक सेकंड रुककर फिर बटन दबाएँ।");
    }
  }

  function stopListening() {
    recognitionRef.current?.stop(); // jo bola hai uska final result de kar rukega
  }

  function clearText() {
    setFinalText("");
    setInterimText("");
    setError("");
  }

  const hasText = finalText || interimText;

  return (
    <main className="min-h-dvh bg-ink px-4 py-10 text-[18px] text-white sm:px-6">
      <div className="mx-auto w-full max-w-xl">
        <h1 className="text-3xl font-bold">🎙️ आवाज़ से टेक्स्ट</h1>
        <p className="mt-2 text-muted">
          बटन दबाएँ और बोलें। सब कुछ आपके browser में ही होता है, कोई सर्वर या API key नहीं।
        </p>

        {/* Browser support na ho to ye message */}
        {supported === false && (
          <div role="alert" className="mt-6 rounded-xl border border-red-400/40 bg-red-500/10 p-4 text-red-200">
            माफ़ कीजिए, आपका browser आवाज़ पहचानना (Web Speech API) सपोर्ट नहीं करता। कृपया Android या
            कंप्यूटर पर <strong>Google Chrome</strong> का नया version इस्तेमाल करें।
          </div>
        )}

        {/* Language dropdown */}
        <label htmlFor="lang" className="mt-8 block font-medium">
          भाषा चुनें
        </label>
        <select
          id="lang"
          value={lang}
          onChange={(e) => setLang(e.target.value)}
          disabled={listening} // sunte waqt bhasha nahi badal sakte
          className="mt-2 min-h-14 w-full rounded-xl border border-line bg-panel px-4 text-[18px] text-white disabled:opacity-50"
        >
          {LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>

        {/* Buttons */}
        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={startListening}
            disabled={listening || supported !== true}
            className="min-h-14 flex-1 rounded-xl bg-white px-6 text-[18px] font-semibold text-ink transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {listening ? "🔴 सुन रहा हूँ…" : "🎤 बोलना शुरू करें"}
          </button>

          {listening && (
            <button
              type="button"
              onClick={stopListening}
              className="min-h-14 rounded-xl border border-line bg-panel px-6 text-[18px] font-semibold"
            >
              ⏹ रोको
            </button>
          )}

          <button
            type="button"
            onClick={clearText}
            disabled={!hasText && !error}
            className="min-h-14 rounded-xl border border-line bg-panel px-6 text-[18px] font-semibold disabled:opacity-50"
          >
            🧹 साफ़ करो
          </button>
        </div>

        {/* Error message (aria-live: screen reader bhi padhega) */}
        <div aria-live="polite">
          {error && (
            <p role="alert" className="mt-6 rounded-xl border border-amber-400/40 bg-amber-500/10 p-4 text-amber-100">
              ⚠️ {error}
            </p>
          )}
        </div>

        {/* Text output: pakka text normal, live text halka (italic) */}
        <section
          aria-label="पहचाना गया टेक्स्ट"
          aria-live="polite"
          className="mt-6 min-h-48 whitespace-pre-wrap break-words rounded-xl border border-line bg-panel p-4 text-[20px] leading-relaxed"
        >
          {hasText ? (
            <>
              <span>{finalText}</span>
              {interimText && <span className="italic text-muted"> {interimText}</span>}
            </>
          ) : (
            <span className="text-muted">यहाँ आपका बोला हुआ टेक्स्ट दिखेगा…</span>
          )}
        </section>
      </div>
    </main>
  );
}
