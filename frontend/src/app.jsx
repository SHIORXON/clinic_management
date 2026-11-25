const {
  useState, useEffect, useRef, useCallback, useContext, createContext, forwardRef, useImperativeHandle,
} = React;
const {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid
} = Recharts;

// Ranglar palitrasi (asl dizayndagi bilan bir xil)
const C = {
  ink: "#132A2E",
  inkSoft: "#1D3B40",
  paper: "#F5F2EB",
  card: "#FFFFFF",
  border: "#E6E1D6",
  text: "#1E2422",
  muted: "#736C5E",
  gold: "#BD9A4B",
  goldSoft: "#F1E7CE",
  teal: "#2F6F63",
  tealSoft: "#E1EEEA",
  red: "#A6483C",
  redSoft: "#F3E1DE",
  amber: "#B8860B",
  amberSoft: "#F6EAD2",
  green: "#3F7D3A",
  greenSoft: "#E3EFE1",
};

// =====================================================================
//  API yordamchilari
// =====================================================================
const FIELD_LABELS = {
  username: "Login", password: "Parol", full_name: "F.I.Sh.", phone: "Telefon", position: "Lavozim",
  department: "Bo'lim", schedule: "Ish jadvali", role: "Rol", hired_at: "Ishga qabul sanasi", name: "Nomi",
  start_time: "Boshlanish vaqti", end_time: "Tugash vaqti", grace_minutes: "Imtiyoz", work_days: "Ish kunlari",
  latitude: "Kenglik", longitude: "Uzunlik", radius_m: "Radius", max_accuracy_m: "GPS aniqligi",
  face_mode: "Yuz rejimi", title: "Mazmuni", description: "Tavsif", due_date: "Muddat", start_date: "Boshlanish", assignees: "Xodimlar", amount: "Summa", reason: "Sabab", date: "Sana", kind: "Turi", comment: "Izoh", file: "Fayl", note: "Izoh", employee: "Xodim", old_password: "Joriy parol", new_password: "Yangi parol",
};

// Django/DRF standart (inglizcha) xabarlarini o'zbekchaga o'giradi. Bizning o'z xabarlarimiz allaqachon o'zbekcha.
const MSG_TRANSLATIONS = [
  [/This field is required/i, () => "Majburiy maydon."],
  [/This field may not be (blank|null)/i, () => "Bo'sh bo'lishi mumkin emas."],
  [/This password is too short\. It must contain at least (\d+)/i, (m) => `Parol juda qisqa: kamida ${m[1]} belgi bo'lishi kerak.`],
  [/This password is too common/i, () => "Bu parol juda oddiy. Murakkabroq parol tanlang."],
  [/This password is entirely numeric/i, () => "Parol faqat raqamlardan iborat bo'lmasin."],
  [/The password is too similar/i, () => "Parol login yoki ismga juda o'xshash."],
  [/A valid integer is required/i, () => "Butun son kiriting."],
  [/A valid number is required|Enter a number/i, () => "Son kiriting."],
  [/greater than or equal to ([\d.-]+)/i, (m) => `Qiymat kamida ${m[1]} bo'lishi kerak.`],
  [/less than or equal to ([\d.-]+)/i, (m) => `Qiymat ko'pi bilan ${m[1]} bo'lishi kerak.`],
  [/no more than (\d+) characters/i, (m) => `Eng ko'pi bilan ${m[1]} belgi kiritish mumkin.`],
  [/Ensure that there are no more than/i, () => "Raqamlar soni juda ko'p."],
  [/(Time|Date|Datetime) has wrong format|Enter a valid (date|time)/i, () => "Sana yoki vaqt formati noto'g'ri."],
  [/Invalid pk|object does not exist|is not a valid choice/i, () => "Tanlangan qiymat topilmadi."],
  [/already exists|must be unique/i, () => "Bunday qiymat allaqachon mavjud."],
  [/Authentication credentials were not provided/i, () => "Tizimga qayta kiring."],
  [/You do not have permission/i, () => "Bu amal uchun ruxsatingiz yo'q."],
  [/Request was throttled/i, () => "Juda ko'p so'rov yuborildi. Biroz kutib turing."],
  [/Method .* not allowed/i, () => "Bu amal mumkin emas."],
  [/^Not found\.?$/i, () => "Topilmadi."],
  [/Enter a valid|Invalid/i, () => "Qiymat noto'g'ri formatda kiritilgan."],
];
function tr(msg) {
  const s = String(msg);
  for (const [re, fn] of MSG_TRANSLATIONS) {
    const m = s.match(re);
    if (m) return fn(m);
  }
  return s;
}

function firstError(data) {
  if (!data || typeof data !== "object") return null;
  for (const [key, val] of Object.entries(data)) {
    const raw = Array.isArray(val) ? val[0] : typeof val === "string" ? val : null;
    const msg = raw ? tr(raw) : null;
    if (msg) {
      if (key === "detail" || key === "non_field_errors" || key === "code") return String(msg);
      return `${FIELD_LABELS[key] || key}: ${msg}`;
    }
  }
  return null;
}

class ApiError extends Error {
  constructor(status, data) {
    super(firstError(data) || (status === 0 ? "Serverga ulanib bo'lmadi." : "Xatolik yuz berdi."));
    this.status = status;
    this.data = data;
  }
}

let onUnauthorized = () => {};

function getCookie(name) {
  const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : "";
}

async function api(method, url, body) {
  const opts = {
    method,
    credentials: "same-origin",
    headers: { "X-CSRFToken": getCookie("csrftoken"), Accept: "application/json" },
  };
  if (body instanceof FormData) {
    opts.body = body;
  } else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(url, opts);
  } catch (e) {
    throw new ApiError(0, null);
  }
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch (e) { /* JSON emas */ }
  if (!res.ok) {
    if ((res.status === 401 || res.status === 403) && !url.startsWith("/api/auth/login")) {
      // 403 sessiya tugaganini ham, ruxsat yo'qligini ham bildirishi mumkin: sessiyani tekshiramiz.
      try {
        const me = await fetch("/api/auth/me/", { credentials: "same-origin" });
        if (me.status === 401 || me.status === 403) onUnauthorized();
      } catch (e) { /* tarmoq xatosi */ }
    }
    throw new ApiError(res.status, data);
  }
  return data;
}

async function apiAll(url) {
  let out = [];
  let next = url;
  let guard = 0;
  while (next && guard++ < 50) {
    const data = await api("GET", next);
    if (Array.isArray(data)) return data;
    out = out.concat(data.results);
    if (data.next) {
      const u = new URL(data.next, window.location.origin);
      next = u.pathname + u.search;
    } else {
      next = null;
    }
  }
  return out;
}

function qs(params) {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== "" && v !== null && v !== undefined) p.append(k, v);
  });
  const s = p.toString();
  return s ? "?" + s : "";
}

// =====================================================================
//  Formatlash
// =====================================================================
const MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"];
const DAY_NAMES = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"];

function fmtLongDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  return `${d}-${MONTHS[m - 1]} ${y}`;
}
function fmtDate(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}
function fmtTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}
function relTime(iso) {
  const diff = Math.max(0, (Date.now() - new Date(iso).getTime()) / 60000);
  if (diff < 1) return "hozirgina";
  if (diff < 60) return `${Math.floor(diff)} daqiqa oldin`;
  if (diff < 60 * 24) return `${Math.floor(diff / 60)} soat oldin`;
  if (diff < 60 * 48) return "kecha";
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
}
function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
// Bugundan 7 kun oldingi sana (filtrlarning boshlang'ich qiymati: oxirgi hafta)
function weekAgoISO() {
  const d = new Date();
  d.setDate(d.getDate() - 7);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function hhmm(t) { return t ? String(t).slice(0, 5) : ""; }
function daysLabel(work_days) {
  return (work_days || "").split(",").filter((x) => x !== "").map((i) => DAY_NAMES[Number(i)]).join(", ");
}

// =====================================================================
//  Umumiy hooklar va kontekst
// =====================================================================
const ToastCtx = createContext(() => {});

function ToastHost({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((text, type = "ok") => {
    const id = Math.random();
    setItems((p) => [...p, { id, text, type }]);
    setTimeout(() => setItems((p) => p.filter((i) => i.id !== id)), 4500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 left-4 sm:left-auto z-[60] flex flex-col gap-2 items-end pointer-events-none">
        {items.map((t) => (
          <div
            key={t.id}
            className="rounded-xl px-4 py-3 shadow-lg text-white flex items-center gap-2 max-w-sm"
            style={{ background: t.type === "error" ? C.red : C.ink, fontSize: 13, fontWeight: 500 }}
          >
            <Icon name={t.type === "error" ? "alert-triangle" : "circle-check"} size={16} color={t.type === "error" ? "#fff" : C.gold} />
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

function useLoad(fn, deps) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fn()
      .then((data) => alive && setState({ data, loading: false, error: null }))
      .catch((e) => alive && setState({ data: null, loading: false, error: e.message || "Xatolik yuz berdi." }));
    return () => { alive = false; };
    // eslint-disable-next-line
  }, [...deps, tick]);
  return { ...state, reload: () => setTick((t) => t + 1) };
}

function useDebounced(value, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

// =====================================================================
//  Asosiy UI komponentlari (asl dizayndan)
// =====================================================================
// Ruxsat tekshiruvi (administrator hammasiga ega)
function can(user, code) {
  return !!user && (user.is_admin || (user.permissions || []).includes(code));
}
function roleLabel(user) {
  if (user.is_admin) return "Administrator";
  const n = (user.permissions || []).length;
  return n ? "Xodim · boshqaruv huquqi bor" : "Xodim";
}

function toPascal(name) {
  return name.split("-").map((s) => s.charAt(0).toUpperCase() + s.slice(1)).join("");
}

// Lucide ikonkasini to'g'ridan-to'g'ri React SVG sifatida chizadi (DOM'ni qo'lda almashtirmaydi,
// shuning uchun React bilan to'qnashmaydi).
function Icon({ name, size = 16, color = "currentColor", className = "" }) {
  const node = window.lucide && window.lucide.icons && window.lucide.icons[toPascal(name)];
  if (!node) return <span className={`inline-block ${className}`} style={{ width: size, height: size }} />;
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      className={`inline-block ${className}`} style={{ flexShrink: 0 }} aria-hidden="true"
    >
      {node.map(([tag, attrs], i) => {
        const { key, ...rest } = attrs;
        return React.createElement(tag, { key: i, ...rest });
      })}
    </svg>
  );
}

function Sidebar({ nav, bottom, active, setActive, user, onLogout }) {
  const initial = (user.full_name || "?").trim().charAt(0).toUpperCase();
  const short = (() => {
    const p = (user.full_name || "").trim().split(/\s+/);
    return p.length > 1 ? `${p[0]} ${p[1].charAt(0)}.` : p[0];
  })();
  const bottomActive = active === bottom.id;
  return (
    <div className="h-full flex flex-col justify-between" style={{ background: C.ink, width: 264 }}>
      <div>
        <div className="flex items-center gap-3 px-6" style={{ height: 76, borderBottom: `1px solid ${C.inkSoft}` }}>
          <div className="flex items-center justify-center rounded-full" style={{ width: 36, height: 36, background: C.gold }}>
            <span style={{ color: C.ink, fontWeight: 700, fontSize: 16 }}>G</span>
          </div>
          <div>
            <div style={{ color: "#F7F3E8", fontSize: 17, letterSpacing: 0.3, fontWeight: 600 }}>Gold Med</div>
            <div style={{ color: "#9FB3AE", fontSize: 10, letterSpacing: 1.2, textTransform: "uppercase" }}>Boshqaruv</div>
          </div>
        </div>

        <nav className="px-3 py-4 flex flex-col gap-1">
          {nav.map((item) => {
            if (item.heading) {
              return <div key={item.heading} className="px-3 pt-4 pb-1" style={{ color: "#6F8680", fontSize: 10.5, letterSpacing: 1.2, textTransform: "uppercase", fontWeight: 600 }}>{item.heading}</div>;
            }
            const isActive = active === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActive(item.id)}
                className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors w-full"
                style={{
                  background: isActive ? C.inkSoft : "transparent",
                  color: isActive ? "#F7F3E8" : "#B7C4C0",
                  borderLeft: isActive ? `3px solid ${C.gold}` : "3px solid transparent",
                }}
              >
                <Icon name={item.icon} size={17} />
                <span style={{ fontSize: 13.5, fontWeight: isActive ? 600 : 500, flex: 1 }}>{item.label}</span>
                {item.badge > 0 && <span className="rounded-full text-center" style={{ background: C.gold, color: C.ink, fontSize: 11, fontWeight: 700, minWidth: 20, padding: "1px 6px" }}>{item.badge}</span>}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="px-3 pb-4">
        <button
          onClick={() => setActive(bottom.id)}
          className="flex items-center gap-3 rounded-lg px-3 py-2.5 w-full text-left mb-2"
          style={{ color: bottomActive ? "#F7F3E8" : "#B7C4C0", background: bottomActive ? C.inkSoft : "transparent" }}
        >
          <Icon name={bottom.icon} size={17} />
          <span style={{ fontSize: 13.5, fontWeight: 500 }}>{bottom.label}</span>
        </button>
        <div className="flex items-center gap-3 rounded-lg px-3 py-3" style={{ background: C.inkSoft }}>
          <div className="rounded-full flex items-center justify-center" style={{ width: 32, height: 32, background: C.gold, color: C.ink, fontWeight: 700, fontSize: 13, flexShrink: 0 }}>
            {initial}
          </div>
          <div style={{ lineHeight: 1.2, flex: 1, minWidth: 0 }}>
            <div className="truncate" style={{ color: "#F7F3E8", fontSize: 12.5, fontWeight: 600 }}>{short}</div>
            <div style={{ color: "#8FA29D", fontSize: 11 }}>{roleLabel(user)}</div>
          </div>
          <button onClick={onLogout} title="Tizimdan chiqish" aria-label="Tizimdan chiqish" className="rounded-lg p-1.5 hover:bg-white/10" style={{ color: "#B7C4C0" }}>
            <Icon name="log-out" size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

function TopBar({ title, subtitle, onMenu, search, setSearch, bell }) {
  return (
    <div className="flex items-center justify-between px-4 md:px-8 gap-3" style={{ height: 76, borderBottom: `1px solid ${C.border}`, background: C.card, flexShrink: 0 }}>
      <div className="flex items-center gap-3 min-w-0">
        <button onClick={onMenu} aria-label="Menyu" className="md:hidden rounded-lg p-2" style={{ background: C.paper, border: `1px solid ${C.border}` }}>
          <Icon name="menu" size={18} color={C.text} />
        </button>
        <div className="min-w-0">
          <div className="truncate" style={{ fontSize: 21, color: C.text, fontWeight: 600 }}>{title}</div>
          {subtitle && <div className="truncate" style={{ fontSize: 12.5, color: C.muted, marginTop: 2 }}>{subtitle}</div>}
        </div>
      </div>
      <div className="flex items-center gap-3">
      {setSearch && (
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 rounded-full px-3.5 py-2" style={{ background: C.paper, border: `1px solid ${C.border}` }}>
            <Icon name="search" size={15} color={C.muted} />
            <input
              placeholder="Qidirish..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-24 sm:w-40"
              style={{ background: "transparent", border: "none", outline: "none", fontSize: 13, color: C.text }}
            />
          </div>
        </div>
      )}
      {bell}
      </div>
    </div>
  );
}

function StatCard({ label, value, delta, positive, icon, accent }) {
  return (
    <div className="rounded-2xl p-5 flex-1 transition-all hover:shadow-md" style={{ background: C.card, border: `1px solid ${C.border}` }}>
      <div className="flex items-center justify-between mb-4">
        <div className="rounded-xl flex items-center justify-center" style={{ width: 38, height: 38, background: accent + "22" }}>
          <Icon name={icon} size={18} color={accent} />
        </div>
        <div className="flex items-center gap-1" style={{ color: positive ? C.green : C.red, fontSize: 12, fontWeight: 600 }}>
          <Icon name={positive ? "arrow-up-right" : "arrow-down-right"} size={13} />
          {delta}
        </div>
      </div>
      <div style={{ fontSize: 28, color: C.text, fontWeight: 600 }}>{value}</div>
      <div style={{ fontSize: 12.5, color: C.muted, marginTop: 2 }}>{label}</div>
    </div>
  );
}

function Badge({ text, bg, fg }) {
  return (
    <span className="rounded-full px-2.5 py-1 inline-block whitespace-nowrap" style={{ background: bg, color: fg, fontSize: 11.5, fontWeight: 600 }}>
      {text}
    </span>
  );
}

function SectionCard({ title, action, children }) {
  return (
    <div className="rounded-2xl mb-6" style={{ background: C.card, border: `1px solid ${C.border}` }}>
      <div className="flex items-center justify-between gap-3 flex-wrap px-6 pt-5 pb-4">
        <div style={{ fontSize: 16.5, color: C.text, fontWeight: 600 }}>{title}</div>
        {action}
      </div>
      {children}
    </div>
  );
}

// ---- Forma elementlari (asl TaskModal uslubida) ----
const inputCls = "w-full p-3 rounded-lg border focus:outline-none focus:ring-2 focus:ring-[#2F6F63]/30 bg-white";
const labelCls = "block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1";
const inputStyle = { borderColor: C.border };

function Field({ label, children, hint }) {
  return (
    <div>
      <label className={labelCls}>{label}</label>
      {children}
      {hint && <div className="text-xs mt-1" style={{ color: C.muted }}>{hint}</div>}
    </div>
  );
}

function PrimaryBtn({ children, busy, disabled, icon, ...rest }) {
  return (
    <button
      {...rest}
      disabled={busy || disabled}
      className="flex items-center justify-center gap-1.5 px-5 py-2.5 rounded-lg font-semibold text-white shadow-md hover:shadow-lg disabled:opacity-60 disabled:cursor-not-allowed transition-transform active:scale-95"
      style={{ background: C.ink, fontSize: 13.5 }}
    >
      {icon && <Icon name={icon} size={14} color="#fff" />}
      {busy ? "Kuting..." : children}
    </button>
  );
}
function GhostBtn({ children, ...rest }) {
  return (
    <button {...rest} className="px-4 py-2.5 rounded-lg font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 disabled:opacity-60" style={{ fontSize: 13.5 }}>
      {children}
    </button>
  );
}
// Faqat ikonkali tugma (tahrirlash, o'chirish va h.k.): title va aria-label bilan
function IconBtn({ icon, title, color = "#64748B", ...rest }) {
  return (
    <button type="button" title={title} aria-label={title} className="p-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-50" {...rest}>
      <Icon name={icon} size={16} color={color} />
    </button>
  );
}
function DangerBtn({ children, busy, ...rest }) {
  return (
    <button {...rest} disabled={busy} className="px-5 py-2.5 rounded-lg font-semibold text-white shadow-md disabled:opacity-60" style={{ background: C.red, fontSize: 13.5 }}>
      {busy ? "Kuting..." : children}
    </button>
  );
}

function ErrorBox({ text }) {
  if (!text) return null;
  return (
    <div className="rounded-lg px-3 py-2.5 text-sm flex gap-2 items-start" style={{ background: C.redSoft, color: C.red }} role="alert">
      <Icon name="alert-triangle" size={15} className="mt-0.5" />
      <span>{text}</span>
    </div>
  );
}

function StateBox({ loading, error, onRetry, children, empty }) {
  if (loading && !children) return <div className="text-center py-10 text-slate-400 text-sm">Yuklanmoqda...</div>;
  if (error) {
    return (
      <div className="text-center py-10 text-sm" style={{ color: C.red }}>
        {error}
        {onRetry && <div className="mt-3"><GhostBtn onClick={onRetry}>Qayta urinish</GhostBtn></div>}
      </div>
    );
  }
  if (empty) return <div className="text-center py-10 text-slate-400 text-sm">{empty}</div>;
  return children;
}

function Modal({ title, icon, onClose, children, maxWidth = "max-w-md" }) {
  useEffect(() => {
    const h = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex bg-black/50 backdrop-blur-sm overflow-y-auto py-6" role="dialog" aria-modal="true">
      <div className={`bg-white rounded-2xl w-full ${maxWidth} p-6 shadow-2xl mx-4 sm:mx-auto my-auto`} style={{ border: `1px solid ${C.border}` }}>
        <div className="flex justify-between items-center mb-5 pb-3" style={{ borderBottom: `1px solid ${C.border}` }}>
          <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
            {icon && <Icon name={icon} size={20} color={C.teal} />} {title}
          </h3>
          <button onClick={onClose} aria-label="Yopish" className="text-slate-400 hover:text-slate-600">
            <Icon name="x" size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function ConfirmModal({ title, text, confirmLabel, danger, onConfirm, onClose }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = async () => {
    setBusy(true);
    setError("");
    try { await onConfirm(); } catch (e) { setError(e.message); setBusy(false); }
  };
  return (
    <Modal title={title} icon="alert-triangle" onClose={onClose}>
      <div className="flex flex-col gap-4 text-sm">
        <div style={{ color: C.text, lineHeight: 1.55 }}>{text}</div>
        <ErrorBox text={error} />
        <div className="flex gap-3 justify-end pt-3" style={{ borderTop: `1px solid ${C.border}` }}>
          <GhostBtn type="button" onClick={onClose}>Bekor qilish</GhostBtn>
          {danger ? <DangerBtn busy={busy} onClick={run}>{confirmLabel}</DangerBtn> : <PrimaryBtn busy={busy} onClick={run}>{confirmLabel}</PrimaryBtn>}
        </div>
      </div>
    </Modal>
  );
}

function Pager({ page, count, size = 50, onPage }) {
  const pages = Math.max(1, Math.ceil(count / size));
  if (pages <= 1) return null;
  return (
    <div className="flex items-center justify-between px-6 pb-5 text-sm" style={{ color: C.muted }}>
      <span>Jami: {count}</span>
      <div className="flex items-center gap-2">
        <GhostBtn disabled={page <= 1} onClick={() => onPage(page - 1)}>Oldingi</GhostBtn>
        <span>{page} / {pages}</span>
        <GhostBtn disabled={page >= pages} onClick={() => onPage(page + 1)}>Keyingi</GhostBtn>
      </div>
    </div>
  );
}

const ATT_STYLE = {
  on_time: { bg: C.greenSoft, fg: C.green },
  late: { bg: C.redSoft, fg: C.red },
  absent: { bg: C.amberSoft, fg: C.amber },
};

// =====================================================================
//  Kirish (login)
// =====================================================================
function Login({ onLoggedIn }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const me = await api("POST", "/api/auth/login/", { username, password });
      onLoggedIn(me);
    } catch (err) {
      setError(err.status === 429 ? "Juda ko'p urinish. Bir daqiqadan keyin qayta urinib ko'ring." : err.message);
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10" style={{ background: C.paper }}>
      <div className="w-full max-w-sm rounded-2xl overflow-hidden shadow-xl" style={{ background: C.card, border: `1px solid ${C.border}` }}>
        <div className="flex items-center gap-3 px-6" style={{ height: 76, background: C.ink }}>
          <div className="flex items-center justify-center rounded-full" style={{ width: 36, height: 36, background: C.gold }}>
            <span style={{ color: C.ink, fontWeight: 700, fontSize: 16 }}>G</span>
          </div>
          <div>
            <div style={{ color: "#F7F3E8", fontSize: 17, letterSpacing: 0.3, fontWeight: 600 }}>Gold Med</div>
            <div style={{ color: "#9FB3AE", fontSize: 10, letterSpacing: 1.2, textTransform: "uppercase" }}>Boshqaruv</div>
          </div>
        </div>
        <form onSubmit={submit} className="p-6 flex flex-col gap-4 text-sm">
          <div>
            <div style={{ fontSize: 19, fontWeight: 600, color: C.text }}>Tizimga kirish</div>
            <div style={{ fontSize: 12.5, color: C.muted, marginTop: 2 }}>Login va parolingizni kiriting</div>
          </div>
          <Field label="Login">
            <input className={inputCls} style={inputStyle} value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoCapitalize="none" autoFocus required />
          </Field>
          <Field label="Parol">
            <input className={inputCls} style={inputStyle} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </Field>
          <ErrorBox text={error} />
          <PrimaryBtn type="submit" busy={busy}>Kirish</PrimaryBtn>
        </form>
      </div>
    </div>
  );
}

// =====================================================================
//  Administrator: boshqaruv paneli
// =====================================================================
function Dashboard({ onNavigate }) {
  const { data, loading, error, reload } = useLoad(() => api("GET", "/api/reports/dashboard/"), []);
  useEffect(() => {
    const t = setInterval(reload, 60000);
    return () => clearInterval(t);
  }, []);

  if (!data) return <StateBox loading={loading} error={error} onRetry={reload} />;

  const base = data.expected_today || data.total_employees || 0;
  const pct = (n) => (base ? `${Math.round((n / base) * 100)}%` : "0%");

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col md:flex-row gap-5">
        <StatCard label="Faol xodimlar" value={data.total_employees} delta={`bugun jadvalda: ${data.expected_today}`} positive icon="users" accent={C.gold} />
        <StatCard label="Bugun ishga kelgan" value={data.present_today} delta={pct(data.present_today)} positive icon="user-check" accent={C.teal} />
        <StatCard label="Kechikkan" value={data.late_today} delta={pct(data.late_today)} positive={data.late_today === 0} icon="timer" accent={C.amber} />
        <StatCard label="Ishga kelmagan" value={data.absent_today} delta={pct(data.absent_today)} positive={data.absent_today === 0} icon="user-x" accent={C.red} />
      </div>

      <div className="flex flex-col md:flex-row gap-5">
        <StatCard label="Jarayondagi topshiriqlar" value={data.tasks_in_progress} delta={`tekshiruvda: ${data.tasks_to_review}`} positive icon="clipboard-list" accent={C.teal} />
        <StatCard label="Muddati o'tgan topshiriqlar" value={data.tasks_overdue} delta="ochiq" positive={data.tasks_overdue === 0} icon="clock" accent={C.red} />
        <StatCard label="Bonuslar (shu oy)" value={data.bonus_count_month} delta={money(data.bonus_sum_month)} positive icon="gift" accent={C.gold} />
        <StatCard label="Ogohlantirish/jarima (shu oy)" value={data.discipline_count_month} delta="yozuv" positive={data.discipline_count_month === 0} icon="triangle-alert" accent={C.amber} />
      </div>

      <div className="flex flex-col lg:flex-row gap-5">
        <div style={{ flex: 1.4 }}>
          <SectionCard title="Haftalik davomat dinamikasi" action={<Badge text="Bu hafta" bg={C.goldSoft} fg={C.gold} />}>
            <div className="px-4 pb-5" style={{ height: 230 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.weekly} barGap={4}>
                  <CartesianGrid vertical={false} stroke={C.border} />
                  <XAxis dataKey="day" tick={{ fontSize: 11.5, fill: C.muted }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11.5, fill: C.muted }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: `1px solid ${C.border}` }} />
                  <Bar dataKey="kelgan" fill={C.goldSoft} radius={[4, 4, 0, 0]} name="Kelgan" />
                  <Bar dataKey="vaqtida" fill={C.teal} radius={[4, 4, 0, 0]} name="O'z vaqtida" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </SectionCard>
        </div>

        <div style={{ flex: 1 }}>
          <SectionCard title="Topshiriqlar dinamikasi" action={<Badge text="Bu hafta" bg={C.goldSoft} fg={C.gold} />}>
            <div className="px-4 pb-5" style={{ height: 230 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.tasks_weekly} barGap={4}>
                  <CartesianGrid vertical={false} stroke={C.border} />
                  <XAxis dataKey="day" tick={{ fontSize: 11.5, fill: C.muted }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11.5, fill: C.muted }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: `1px solid ${C.border}` }} />
                  <Bar dataKey="berilgan" fill={C.goldSoft} radius={[4, 4, 0, 0]} name="Berilgan" />
                  <Bar dataKey="bajarilgan" fill={C.teal} radius={[4, 4, 0, 0]} name="Tasdiqlangan" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </SectionCard>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-5">
        <div style={{ flex: 1 }}>
          <SectionCard title="So'nggi faoliyat jurnali">
            <div className="px-6 pb-5 flex flex-col gap-4 max-h-[230px] overflow-y-auto">
              {data.activity.length === 0 && <div className="text-sm text-slate-400">Hozircha faoliyat yo'q.</div>}
              {data.activity.map((a, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="rounded-full flex-shrink-0 w-2 h-2 mt-1.5" style={{ background: C.gold }} />
                  <div style={{ fontSize: 12.8, color: C.text, lineHeight: 1.5 }}>
                    <span style={{ fontWeight: 600 }}>{a.who}</span> {a.what}
                    <div style={{ color: C.muted, fontSize: 11.5, marginTop: 1 }}>{relTime(a.when)}</div>
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  );
}

// =====================================================================
//  Kamera (yuz olish) va joylashuv
// =====================================================================
const CameraCapture = forwardRef(function CameraCapture({ onState }, ref) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [state, setState] = useState("starting");
  const [err, setErr] = useState("");

  const update = (s, message = "") => { setState(s); setErr(message); onState && onState(s); };

  useEffect(() => {
    let stopped = false;
    (async () => {
      if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        update("error", "Kamera faqat HTTPS yoki localhost orqali ishlaydi. Manzil satrini tekshiring.");
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } }, audio: false,
        });
        if (stopped) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;
        videoRef.current.srcObject = stream;
        try { await videoRef.current.play(); } catch (e) { /* autoplay */ }
        update("ready");
      } catch (e) {
        const msg = e && e.name === "NotAllowedError"
          ? "Kameraga ruxsat berilmadi. Brauzer sozlamalarida kameraga ruxsat bering va qayta urinib ko'ring."
          : e && e.name === "NotFoundError"
            ? "Kamera topilmadi."
            : "Kamerani ochib bo'lmadi. Boshqa dastur kamerani ishlatayotgan bo'lishi mumkin.";
        update("error", msg);
      }
    })();
    return () => {
      stopped = true;
      if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop());
    };
  }, []);

  useImperativeHandle(ref, () => ({
    capture: () => new Promise((resolve, reject) => {
      const v = videoRef.current;
      if (!v || !v.videoWidth) { reject(new Error("Kamera hali tayyor emas.")); return; }
      const scale = Math.min(1, 640 / v.videoWidth);
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(v.videoWidth * scale);
      canvas.height = Math.round(v.videoHeight * scale);
      canvas.getContext("2d").drawImage(v, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("Suratga olib bo'lmadi."))), "image/jpeg", 0.85);
    }),
  }), []);

  return (
    <div>
      <div className="rounded-xl overflow-hidden relative" style={{ background: "#000", aspectRatio: "4 / 3" }}>
        <video ref={videoRef} playsInline muted autoPlay className="w-full h-full" style={{ objectFit: "cover", transform: "scaleX(-1)" }} />
        {state === "starting" && <div className="absolute inset-0 flex items-center justify-center text-white text-sm">Kamera yoqilmoqda...</div>}
      </div>
      {err && <div className="mt-3"><ErrorBox text={err} /></div>}
    </div>
  );
});

const GEO_ERR = {
  1: "Joylashuvga ruxsat berilmadi. Brauzer sozlamalarida (manzil satridagi qulf belgisi) joylashuvga ruxsat bering va qayta urinib ko'ring.",
  2: "Joylashuvni aniqlab bo'lmadi. Telefonda GPS (joylashuv xizmati) yoqilganini tekshiring.",
  3: "Joylashuvni aniqlash vaqti tugadi. Ochiq joyda qayta urinib ko'ring.",
};

function getPosition() {
  return new Promise((resolve, reject) => {
    if (!window.isSecureContext) { reject(new Error("Joylashuv faqat HTTPS yoki localhost orqali ishlaydi.")); return; }
    if (!navigator.geolocation) { reject(new Error("Brauzeringiz joylashuvni qo'llab-quvvatlamaydi.")); return; }
    navigator.geolocation.getCurrentPosition(
      resolve,
      (e) => reject(new Error(GEO_ERR[e.code] || "Joylashuvni aniqlab bo'lmadi.")),
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
    );
  });
}

// =====================================================================
//  Xodim: bosh sahifa (ishga keldim / ishdan ketdim)
// =====================================================================
function CheckModal({ action, today, onClose, onDone }) {
  const toast = useContext(ToastCtx);
  const needFace = today.face.will_verify;
  const either = today.check_mode === "either";
  // "Yuz YOKI joylashuv" rejimida va yuz tekshirish mumkin bo'lsa, joylashuv majburiy emas (yuz yetarli).
  const locationRequired = !(either && needFace);
  const camRef = useRef(null);
  const [camState, setCamState] = useState(needFace ? "starting" : "ready");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState("");
  const [error, setError] = useState("");
  const isIn = action === "check_in";
  // Kamera ochilmasa: "yoki" rejimida joylashuv bilan davom etish mumkin, "ikkalasi" rejimida mumkin emas.
  const blocked = camState === "starting" || (camState === "error" && !either);

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const fd = new FormData();
      let haveImage = false;
      if (needFace && camState === "ready") {
        setStep("Yuz suratga olinmoqda...");
        fd.append("image", await camRef.current.capture(), "face.jpg");
        haveImage = true;
      }
      let pos = null;
      setStep("Joylashuv aniqlanmoqda...");
      try {
        pos = await getPosition();
      } catch (e) {
        if (locationRequired || !haveImage) throw e;
        // yuz bor, joylashuv yo'q: serverga faqat yuzni yuboramiz
      }
      if (pos) {
        fd.append("latitude", pos.coords.latitude);
        fd.append("longitude", pos.coords.longitude);
        fd.append("accuracy", pos.coords.accuracy);
      }
      setStep("Server tekshirmoqda...");
      const rec = await api("POST", `/api/attendance/${isIn ? "check-in" : "check-out"}/`, fd);
      const time = fmtTime(isIn ? rec.check_in : rec.check_out);
      toast(isIn ? `Ishga kelganingiz qayd etildi (${time})` : `Ishdan ketganingiz qayd etildi (${time})`);
      onDone();
    } catch (e) {
      setError(e.message);
      setBusy(false);
      setStep("");
    }
  };

  return (
    <Modal title={isIn ? "Ishga keldim" : "Ishdan ketdim"} icon={isIn ? "user-check" : "log-out"} onClose={busy ? () => {} : onClose}>
      <div className="flex flex-col gap-4 text-sm">
        {needFace ? (
          <>
            <div style={{ color: C.muted }}>
              {either
                ? "Davomat yuz YOKI joylashuv bilan tasdiqlanadi: ikkalasidan biri to'g'ri bo'lsa yetarli. Yuzingiz kameraga to'liq ko'ringan holda, yaxshi yoritilgan joyda turing."
                : "Yuzingiz kameraga to'liq ko'ringan holda, yaxshi yoritilgan joyda turing. Joylashuvingiz ham klinika radiusida bo'lishi kerak."}
            </div>
            <CameraCapture ref={camRef} onState={setCamState} />
          </>
        ) : (
          <div className="rounded-lg px-3 py-2.5" style={{ background: C.amberSoft, color: C.amber }}>
            Yuz tekshiruvi sizda ishlamaydi (tizimda sozlanmagan yoki yuzingiz ro'yxatdan o'tkazilmagan): davomat faqat joylashuv bo'yicha qayd etiladi va «yuz tekshirilmagan» deb belgilanadi.
          </div>
        )}
        <div style={{ color: C.muted }}>
          Tugmani bosganingizda brauzer joylashuvingizni so'raydi. Joylashuv faqat shu lahzada olinadi, doimiy kuzatilmaydi.
        </div>
        <ErrorBox text={error} />
        {busy && <div className="text-center" style={{ color: C.teal, fontWeight: 600 }}>{step}</div>}
        <div className="flex gap-3 justify-end pt-3" style={{ borderTop: `1px solid ${C.border}` }}>
          <GhostBtn type="button" onClick={onClose} disabled={busy}>Bekor qilish</GhostBtn>
          <PrimaryBtn busy={busy} disabled={blocked} onClick={submit} icon="map-pin">
            {error ? "Qayta urinish" : "Yuborish"}
          </PrimaryBtn>
        </div>
      </div>
    </Modal>
  );
}

function MiniBox({ label, value, color }) {
  return (
    <div className="rounded-xl p-4" style={{ border: `1px solid ${C.border}`, background: C.paper }}>
      <div style={{ fontSize: 11.5, color: C.muted, textTransform: "uppercase", letterSpacing: 0.8, fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 22, color: color || C.text, fontWeight: 600, marginTop: 6 }}>{value}</div>
    </div>
  );
}

function EmployeeHome({ user, onNavigate }) {
  const { data: today, loading, error, reload } = useLoad(() => api("GET", "/api/attendance/today/"), []);
  const [modal, setModal] = useState(null);

  if (!today) return <StateBox loading={loading} error={error} onRetry={reload} />;
  const rec = today.record;
  const st = rec && ATT_STYLE[rec.status];

  const either = today.check_mode === "either";
  const faceNote = today.face.will_verify
    ? { text: either ? "Davomat yuzingiz YOKI joylashuvingiz orqali tasdiqlanadi (bittasi yetarli)." : "Yuzingiz kamera orqali tekshiriladi va joylashuvingiz klinika radiusida bo'lishi kerak.", ok: true }
    : today.face.available
      ? { text: today.face.mode === "strict" ? "Yuzingiz tizimda ro'yxatdan o'tkazilmagan: davomat qabul qilinmaydi. Administratorga murojaat qiling." : "Yuzingiz tizimda ro'yxatdan o'tkazilmagan: davomat «yuz tekshirilmagan» deb belgilanadi.", ok: false }
      : { text: "Yuz tekshiruvi tizimda hali sozlanmagan: davomat faqat joylashuv bo'yicha qayd etiladi.", ok: false };

  return (
    <>
      <SectionCard title={`Xush kelibsiz, ${user.full_name}`} action={<Badge text={fmtLongDate(today.date)} bg={C.goldSoft} fg={C.gold} />}>
        <div className="px-6 pb-6 flex flex-col gap-5">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <MiniBox label="Ishga kelgan" value={rec ? fmtTime(rec.check_in) : "—"} />
            <MiniBox label="Ishdan ketgan" value={rec ? fmtTime(rec.check_out) : "—"} />
            <div className="rounded-xl p-4 col-span-2 sm:col-span-1" style={{ border: `1px solid ${C.border}`, background: C.paper }}>
              <div style={{ fontSize: 11.5, color: C.muted, textTransform: "uppercase", letterSpacing: 0.8, fontWeight: 600 }}>Holat</div>
              <div style={{ marginTop: 10 }}>
                {rec ? <Badge text={rec.late_minutes ? `${rec.status_label} · ${rec.late_minutes} daq.` : rec.status_label} bg={st.bg} fg={st.fg} /> : <span style={{ color: C.muted, fontSize: 14 }}>Hali kelmadingiz</span>}
              </div>
            </div>
          </div>

          {!today.location_configured && <ErrorBox text="Klinika joylashuvi hali sozlanmagan. Administratorga murojaat qiling." />}

          <div className="flex flex-col sm:flex-row gap-3">
            <button
              disabled={!today.can_check_in || !today.location_configured}
              onClick={() => setModal("check_in")}
              className="flex-1 flex items-center justify-center gap-2 rounded-xl py-4 text-white font-semibold shadow-md disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98] transition-transform"
              style={{ background: C.teal, fontSize: 15 }}
            >
              <Icon name="user-check" size={18} color="#fff" /> Ishga keldim
            </button>
            <button
              disabled={!today.can_check_out || !today.location_configured}
              onClick={() => setModal("check_out")}
              className="flex-1 flex items-center justify-center gap-2 rounded-xl py-4 text-white font-semibold shadow-md disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98] transition-transform"
              style={{ background: C.ink, fontSize: 15 }}
            >
              <Icon name="log-out" size={18} color="#fff" /> Ishdan ketdim
            </button>
          </div>

          <div className="flex flex-col gap-2 text-sm" style={{ color: C.muted }}>
            {today.radius_m && (
              <div className="flex items-start gap-2">
                <Icon name="map-pin" size={15} className="mt-0.5" />
                {either && today.face.will_verify
                  ? `Klinikadan ${today.radius_m} metr radius ichida bo'lsangiz yoki yuzingiz tasdiqlansa, davomat qabul qilinadi.`
                  : `Davomat klinikadan ${today.radius_m} metr radius ichida qayd etiladi.`}
              </div>
            )}
            <div className="flex items-start gap-2" style={{ color: faceNote.ok ? C.teal : C.amber }}>
              <Icon name={faceNote.ok ? "shield-check" : "info"} size={15} className="mt-0.5" /> {faceNote.text}
            </div>
          </div>
        </div>
      </SectionCard>
      <EmployeeSummary onNavigate={onNavigate} />
      {modal && <CheckModal action={modal} today={today} onClose={() => setModal(null)} onDone={() => { setModal(null); reload(); }} />}
    </>
  );
}

// =====================================================================
//  Davomat jadvali (administrator: hammasi, xodim: faqat o'zi)
// =====================================================================
function AttendanceView({ user, search, mgr }) {
  const isAdmin = !!mgr;
  const [from, setFrom] = useState(weekAgoISO());
  const [to, setTo] = useState(todayISO());
  const [dept, setDept] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const q = useDebounced(search);

  useEffect(() => { setPage(1); }, [from, to, dept, status, q]);

  const depts = useLoad(() => (isAdmin ? apiAll("/api/departments/") : Promise.resolve([])), []);
  const { data, loading, error, reload } = useLoad(
    () => api("GET", "/api/attendance/" + qs({ scope: isAdmin ? "all" : "", date_from: from, date_to: to, department: dept, status, search: q, page })),
    [from, to, dept, status, q, page]
  );

  const rows = data ? data.results : [];
  return (
    <SectionCard
      title={isAdmin ? "Davomat yozuvlari" : "Mening davomat tarixim"}
      action={<GhostBtn onClick={() => { setFrom(weekAgoISO()); setTo(todayISO()); setDept(""); setStatus(""); }}>Oxirgi 7 kun</GhostBtn>}
    >
      <div className="px-6 pb-4 grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
        <Field label="Sanadan"><input type="date" className={inputCls} style={inputStyle} value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
        <Field label="Sanagacha"><input type="date" className={inputCls} style={inputStyle} value={to} onChange={(e) => setTo(e.target.value)} /></Field>
        {isAdmin && (
          <Field label="Bo'lim">
            <select className={inputCls} style={inputStyle} value={dept} onChange={(e) => setDept(e.target.value)}>
              <option value="">Barchasi</option>
              {(depts.data || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
        )}
        <Field label="Holat">
          <select className={inputCls} style={inputStyle} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Barchasi</option>
            <option value="on_time">O'z vaqtida</option>
            <option value="late">Kechikdi</option>
          </select>
        </Field>
      </div>
      <StateBox loading={loading && !data} error={error} onRetry={reload} empty={data && rows.length === 0 ? "Tanlangan davr uchun davomat yozuvlari topilmadi." : null}>
        {data && rows.length > 0 && (
          <div className="px-6 pb-5 overflow-x-auto">
            <table className="w-full text-left" style={{ borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  {[...(isAdmin ? ["Xodim"] : []), "Sana", "Kelgan", "Ketgan", "Holat", "Yuz", "Joylashuv"].map((h) => (
                    <th key={h} className="pb-3 pt-1 pr-4 text-slate-500 font-semibold uppercase text-[11px] tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const s = ATT_STYLE[r.status] || ATT_STYLE.on_time;
                  return (
                    <tr key={r.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                      {isAdmin && (
                        <td className="py-3.5 pr-4 text-[13px]">
                          <div className="font-medium text-slate-800">{r.employee_name}</div>
                          <div className="text-[11.5px] text-slate-500">{r.department || "—"}</div>
                        </td>
                      )}
                      <td className="py-3.5 pr-4 text-[12.5px] text-slate-700 whitespace-nowrap">{fmtDate(r.date)}</td>
                      <td className="py-3.5 pr-4 text-[12.5px] text-slate-800 font-medium">{fmtTime(r.check_in)}</td>
                      <td className="py-3.5 pr-4 text-[12.5px] text-slate-800 font-medium">{fmtTime(r.check_out)}</td>
                      <td className="py-3.5 pr-4"><Badge text={r.late_minutes ? `${r.status_label} · ${r.late_minutes} daq.` : r.status_label} bg={s.bg} fg={s.fg} /></td>
                      <td className="py-3.5 pr-4">
                        {r.in_face_verified ? <Badge text="Tasdiqlangan" bg={C.tealSoft} fg={C.teal} /> : <Badge text="Tekshirilmagan" bg={C.amberSoft} fg={C.amber} />}
                      </td>
                      <td className="py-3.5">
                        {r.in_location_ok
                          ? <Badge text={`Radiusda · ${Math.round(r.in_distance_m)} m`} bg={C.tealSoft} fg={C.teal} />
                          : r.in_distance_m != null
                            ? <Badge text={`Tashqarida · ${Math.round(r.in_distance_m)} m`} bg={C.redSoft} fg={C.red} />
                            : <Badge text="Yuborilmagan" bg={C.amberSoft} fg={C.amber} />}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </StateBox>
      {data && <Pager page={page} count={data.count} onPage={setPage} />}
    </SectionCard>
  );
}

// =====================================================================
//  Administrator: xodimlar
// =====================================================================
// Xodimga qaysi menyular ko'rinishi va qanday amallar bajarilishini belgilash
function PermissionPicker({ role, value, onChange, onRole }) {
  const cat = useLoad(() => api("GET", "/api/auth/permissions/"), []);
  if (role === "admin") {
    return (
      <div className="rounded-xl px-4 py-3 text-[12.5px]" style={{ background: C.goldSoft, color: C.text }}>
        Administrator barcha menyularni ko'radi va barcha amallarni bajara oladi. Cheklash uchun rolni «Xodim» qiling va ruxsatlarni tanlang.
      </div>
    );
  }
  if (!cat.data) return <div className="text-xs" style={{ color: C.muted }}>Ruxsatlar yuklanmoqda…</div>;
  const has = (c) => value.includes(c);
  const norm = (arr) => {
    const out = new Set(arr);
    arr.forEach((c) => { if (c.endsWith(".manage")) out.add(c.replace(".manage", ".view")); });
    return cat.data.sections.flatMap((sec) => sec.items.map((i) => i.code)).filter((c) => out.has(c));
  };
  const toggle = (code) => {
    let next = has(code) ? value.filter((c) => c !== code) : [...value, code];
    // "ko'rish" olib tashlansa, shu bo'limdagi "boshqarish" ham olinadi
    if (has(code) && code.endsWith(".view")) next = next.filter((c) => c !== code.replace(".view", ".manage"));
    onChange(norm(next));
  };
  const applyPreset = (pr) => { if (pr.role === "admin") onRole("admin"); else { onRole("employee"); onChange(norm(pr.permissions)); } };
  return (
    <div className="rounded-xl p-4 flex flex-col gap-3" style={{ border: `1px solid ${C.border}`, background: C.paper }}>
      <div>
        <div style={{ fontSize: 12.5, fontWeight: 700, color: C.text }}>Tizimdagi huquqlari</div>
        <div style={{ fontSize: 11.5, color: C.muted, marginTop: 2 }}>Xodim o'z topshiriq, davomat, bonus va jarimalarini doim ko'radi. Quyida unga qo'shimcha qaysi bo'limlar ochilishini tanlang.</div>
      </div>
      <div className="flex gap-1.5 flex-wrap">
        {cat.data.presets.map((pr) => (
          <button type="button" key={pr.id} onClick={() => applyPreset(pr)} className="rounded-full px-3 py-1 text-[11.5px] font-semibold bg-white" style={{ border: `1px solid ${C.border}`, color: C.teal }}>{pr.label}</button>
        ))}
      </div>
      <div className="flex flex-col gap-2.5">
        {cat.data.sections.map((sec) => (
          <div key={sec.key} className="rounded-lg bg-white px-3 py-2.5" style={{ border: `1px solid ${C.border}` }}>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: C.text }}>{sec.label}</div>
            <div className="flex flex-col gap-1 mt-1.5">
              {sec.items.map((it) => (
                <label key={it.code} className="flex items-start gap-2 cursor-pointer" style={{ fontSize: 12.5, color: C.text }}>
                  <input type="checkbox" className="w-4 h-4 mt-0.5" checked={has(it.code)} onChange={() => toggle(it.code)} />
                  <span>{it.label}{it.help ? <span style={{ color: C.muted }}> — {it.help}</span> : null}</span>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmployeeModal({ user, employee, departments, schedules, onClose, onSaved, onDeleteRequest }) {
  const toast = useContext(ToastCtx);
  const isEdit = !!employee;
  const [f, setF] = useState({
    username: "", password: "", full_name: employee ? employee.full_name : "", phone: employee ? employee.phone : "",
    position: employee ? employee.position : "", department: employee && employee.department ? String(employee.department) : "",
    schedule: employee && employee.schedule ? String(employee.schedule) : "", role: employee ? employee.role : "employee",
    hired_at: employee && employee.hired_at ? employee.hired_at : "", is_active: employee ? employee.is_active : true,
  });
  const [perms, setPerms] = useState(employee && employee.permissions ? employee.permissions : []);
  const isAdminUser = !!user.is_admin;
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const body = {
      full_name: f.full_name.trim(), phone: f.phone.trim(), position: f.position.trim(),
      department: f.department ? Number(f.department) : null, schedule: f.schedule ? Number(f.schedule) : null,
      role: f.role, hired_at: f.hired_at || null, is_active: f.is_active,
    };
    if (isAdminUser) body.permissions = f.role === "admin" ? [] : perms;
    if (f.username.trim()) body.username = f.username.trim();
    if (f.password) body.password = f.password;
    try {
      if (isEdit) await api("PATCH", `/api/employees/${employee.id}/`, body);
      else await api("POST", "/api/employees/", body);
      toast(isEdit ? "Xodim ma'lumotlari yangilandi" : "Yangi xodim qo'shildi");
      onSaved();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <Modal title={isEdit ? "Xodimni tahrirlash" : "Yangi xodim qo'shish"} icon={isEdit ? "pencil" : "plus-circle"} onClose={onClose} maxWidth="max-w-lg">
      <form onSubmit={submit} className="flex flex-col gap-4 text-sm">
        <Field label="F.I.Sh."><input className={inputCls} style={inputStyle} value={f.full_name} onChange={set("full_name")} placeholder="Masalan: Nigora Tursunova" required /></Field>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Login" hint={isEdit ? "O'zgartirmasangiz bo'sh qoldiring" : null}>
            <input className={inputCls} style={inputStyle} value={f.username} onChange={set("username")} autoComplete="off" autoCapitalize="none" required={!isEdit} placeholder={isEdit ? employee.username : ""} />
          </Field>
          <Field label={isEdit ? "Yangi parol" : "Parol"} hint={isEdit ? "O'zgartirmasangiz bo'sh qoldiring" : "Kamida 8 belgi"}>
            <div className="relative">
              <input className={inputCls} style={inputStyle} type={showPw ? "text" : "password"} value={f.password} onChange={set("password")} autoComplete="new-password" required={!isEdit} />
              <button type="button" onClick={() => setShowPw(!showPw)} aria-label="Parolni ko'rsatish" className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">
                <Icon name={showPw ? "eye-off" : "eye"} size={16} />
              </button>
            </div>
          </Field>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Telefon"><input className={inputCls} style={inputStyle} value={f.phone} onChange={set("phone")} placeholder="+998901234567" inputMode="tel" /></Field>
          <Field label="Lavozim"><input className={inputCls} style={inputStyle} value={f.position} onChange={set("position")} placeholder="Masalan: Hamshira" required /></Field>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Bo'lim">
            <select className={inputCls} style={inputStyle} value={f.department} onChange={set("department")}>
              <option value="">— tanlanmagan —</option>
              {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
          <Field label="Ish jadvali">
            <select className={inputCls} style={inputStyle} value={f.schedule} onChange={set("schedule")}>
              <option value="">— tanlanmagan —</option>
              {schedules.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {isAdminUser && (
            <Field label="Rol">
              <select className={inputCls} style={inputStyle} value={f.role} onChange={set("role")}>
                <option value="employee">Xodim (ruxsatlar quyida)</option>
                <option value="admin">Administrator (hamma narsa)</option>
              </select>
            </Field>
          )}
          <Field label="Ishga qabul sanasi"><input type="date" className={inputCls} style={inputStyle} value={f.hired_at} onChange={set("hired_at")} /></Field>
        </div>
        {isAdminUser && <PermissionPicker role={f.role} value={perms} onChange={setPerms} onRole={(r) => setF({ ...f, role: r })} />}
        <label className="flex items-center gap-2 cursor-pointer" style={{ color: C.text }}>
          <input type="checkbox" checked={f.is_active} onChange={set("is_active")} className="w-4 h-4" />
          Hisob faol (tizimga kira oladi)
        </label>
        <ErrorBox text={error} />
        <div className="flex gap-3 justify-between items-center mt-2 pt-3 flex-wrap" style={{ borderTop: `1px solid ${C.border}` }}>
          {isEdit ? (
            <IconBtn icon="trash-2" title="To'liq o'chirish" color={C.red} onClick={() => onDeleteRequest(employee)} />
          ) : <span />}
          <div className="flex gap-3">
            <GhostBtn type="button" onClick={onClose}>Bekor qilish</GhostBtn>
            <PrimaryBtn type="submit" busy={busy}>Saqlash</PrimaryBtn>
          </div>
        </div>
      </form>
    </Modal>
  );
}

function FaceModal({ employee, onClose, onChanged }) {
  const toast = useContext(ToastCtx);
  const camRef = useRef(null);
  const fileRef = useRef(null);
  const [camState, setCamState] = useState("starting");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { data, loading, error: loadErr, reload } = useLoad(() => api("GET", `/api/attendance/face/${employee.id}/`), []);

  const send = async (blob, name) => {
    setBusy(true);
    setError("");
    try {
      const fd = new FormData();
      fd.append("image", blob, name);
      await api("POST", `/api/attendance/face/${employee.id}/`, fd);
      toast("Yuz ro'yxatdan o'tkazildi");
      onChanged();
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };
  const fromCamera = async () => {
    try { await send(await camRef.current.capture(), "face.jpg"); } catch (e) { setError(e.message); }
  };

  const rt = data && data.face_runtime;
  const checks = rt && [
    ["FACE_VERIFICATION_ENABLED=True (.env)", rt.enabled_in_settings],
    ["face_recognition kutubxonasi o'rnatilgan", rt.library_installed],
    ["FACE_ENCRYPTION_KEY sozlangan (.env)", rt.key_configured],
  ];

  return (
    <Modal title={`Yuz: ${employee.full_name}`} icon="scan-face" onClose={onClose} maxWidth="max-w-lg">
      <div className="flex flex-col gap-4 text-sm">
        <StateBox loading={loading} error={loadErr} onRetry={reload}>
          {data && !rt.available && (
            <div className="flex flex-col gap-3">
              <div className="rounded-lg px-3 py-2.5" style={{ background: C.amberSoft, color: C.amber }}>
                Yuz verifikatsiyasi hali sozlanmagan, shuning uchun yuzni ro'yxatdan o'tkazib bo'lmaydi. Quyidagilar bajarilishi kerak (README ga qarang):
              </div>
              {checks.map(([label, ok]) => (
                <div key={label} className="flex items-center gap-2" style={{ color: ok ? C.green : C.red }}>
                  <Icon name={ok ? "circle-check" : "circle-x"} size={16} /> {label}
                </div>
              ))}
            </div>
          )}
          {data && rt.available && (
            <>
              <div className="flex items-center gap-2" style={{ color: data.enrolled ? C.green : C.muted }}>
                <Icon name={data.enrolled ? "shield-check" : "info"} size={16} />
                {data.enrolled ? "Yuz ro'yxatdan o'tkazilgan. Yangi rasm olinsa, eskisi almashtiriladi." : "Yuz hali ro'yxatdan o'tkazilmagan."}
              </div>
              <div style={{ color: C.muted }}>Xodim kameraga to'g'ri qarab tursin, kadrda faqat u bo'lsin. Rasm saqlanmaydi, faqat shifrlangan raqamli shablon saqlanadi.</div>
              <CameraCapture ref={camRef} onState={setCamState} />
              <ErrorBox text={error} />
              <div className="flex flex-wrap gap-3 justify-between items-center pt-3" style={{ borderTop: `1px solid ${C.border}` }}>
                {data.enrolled ? <IconBtn icon="trash-2" title="Yuzni o'chirish" color={C.red} onClick={() => setConfirmDelete(true)} /> : <span />}
                <div className="flex gap-3 flex-wrap">
                  <input ref={fileRef} type="file" accept="image/*" hidden onChange={(e) => e.target.files[0] && send(e.target.files[0], e.target.files[0].name)} />
                  <GhostBtn type="button" onClick={() => fileRef.current.click()} disabled={busy}>Fayldan yuklash</GhostBtn>
                  <PrimaryBtn busy={busy} disabled={camState !== "ready"} onClick={fromCamera} icon="camera">Suratga olib saqlash</PrimaryBtn>
                </div>
              </div>
            </>
          )}
        </StateBox>
      </div>
      {confirmDelete && (
        <ConfirmModal
          title="Yuzni o'chirish" confirmLabel="O'chirish" danger
          text={`${employee.full_name} yuz shablonini o'chirmoqchimisiz? Keyin u yuz tekshiruvisiz davomat qiladi (yoki qat'iy rejimda qila olmaydi).`}
          onClose={() => setConfirmDelete(false)}
          onConfirm={async () => { await api("DELETE", `/api/attendance/face/${employee.id}/`); toast("Yuz ma'lumoti o'chirildi"); onChanged(); }}
        />
      )}
    </Modal>
  );
}

function EmployeesView({ search, user }) {
  const canManage = can(user, "employees.manage");
  const toast = useContext(ToastCtx);
  const q = useDebounced(search);
  const [dept, setDept] = useState("");
  const [active, setActive] = useState("");
  const [modal, setModal] = useState(null); // {type, employee}

  const meta = useLoad(() => Promise.all([apiAll("/api/departments/"), apiAll("/api/schedules/")]), []);
  const { data, loading, error, reload } = useLoad(
    () => apiAll("/api/employees/" + qs({ search: q, department: dept, is_active: active })),
    [q, dept, active]
  );
  const departments = meta.data ? meta.data[0] : [];
  const schedules = meta.data ? meta.data[1] : [];
  const close = () => setModal(null);
  const refresh = () => { close(); reload(); meta.reload(); };

  const toggleActive = async (e) => {
    try {
      await api("PATCH", `/api/employees/${e.id}/`, { is_active: !e.is_active });
      toast(e.is_active ? "Xodim faolsizlantirildi" : "Xodim faollashtirildi");
      reload();
    } catch (err) { toast(err.message, "error"); }
  };

  const chips = [["", "Barchasi"], ["true", "Faol"], ["false", "Faolsiz"]];

  return (
    <>
      <SectionCard
        title="Xodimlar ro'yxati"
        action={canManage &&
          <button onClick={() => setModal({ type: "edit", employee: null })} className="flex items-center gap-1.5 rounded-lg px-4 py-2.5 text-white shadow-md hover:scale-[1.02] active:scale-95 transition-transform" style={{ background: C.ink }}>
            <Icon name="plus" size={14} color="#fff" />
            <span style={{ fontSize: 12.5, fontWeight: 600 }}>Yangi xodim</span>
          </button>
        }
      >
        <div className="px-6 flex gap-2 pb-4 flex-wrap items-center">
          {chips.map(([v, label]) => (
            <button key={label} onClick={() => setActive(v)} className="rounded-full px-3 py-1.5 transition-colors text-[12px] font-semibold"
              style={{ background: active === v ? C.ink : C.paper, color: active === v ? "#fff" : C.muted, border: `1px solid ${active === v ? C.ink : C.border}` }}>
              {label}
            </button>
          ))}
          <select value={dept} onChange={(e) => setDept(e.target.value)} className="rounded-full px-3 py-1.5 text-[12px] font-semibold bg-white" style={{ border: `1px solid ${C.border}`, color: C.muted }} aria-label="Bo'lim bo'yicha filtr">
            <option value="">Barcha bo'limlar</option>
            {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
        <div className="px-2 pb-4">
          <StateBox loading={loading && !data} error={error} onRetry={reload} empty={data && data.length === 0 ? "Xodimlar topilmadi." : null}>
            {data && data.map((e, i) => (
              <div key={e.id} className="flex flex-wrap items-center gap-3 px-4 py-3.5 mx-2 rounded-xl hover:bg-slate-50 transition-colors" style={{ borderBottom: i !== data.length - 1 ? `1px solid ${C.border}` : "none" }}>
                <div className="rounded-full flex items-center justify-center text-white font-semibold flex-shrink-0" style={{ width: 38, height: 38, background: e.is_active ? C.teal : C.muted }}>
                  {e.full_name.charAt(0).toUpperCase()}
                </div>
                <div style={{ flex: "1 1 200px", minWidth: 0 }}>
                  <div className="truncate" style={{ fontSize: 13.5, color: C.text, fontWeight: 500, opacity: e.is_active ? 1 : 0.6 }}>{e.full_name}</div>
                  <div className="truncate" style={{ fontSize: 11.5, color: C.muted, marginTop: 3 }}>
                    {e.position} · {e.department_name || "Bo'limsiz"}{e.phone ? ` · ${e.phone}` : ""}
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  {e.role === "admin" && <Badge text="Administrator" bg={C.goldSoft} fg={C.gold} />}
                  {e.role !== "admin" && (e.permissions || []).length > 0 && <Badge text={`${e.permissions.length} ta ruxsat`} bg={C.tealSoft} fg={C.teal} />}
                  <Badge text={e.is_active ? "Faol" : "Faolsiz"} bg={e.is_active ? C.greenSoft : C.redSoft} fg={e.is_active ? C.green : C.red} />
                  <Badge text={e.face_enrolled ? "Yuz bor" : "Yuz yo'q"} bg={e.face_enrolled ? C.tealSoft : C.amberSoft} fg={e.face_enrolled ? C.teal : C.amber} />
                </div>
                {canManage && <div className="flex items-center gap-1">
                  <IconBtn icon="pencil" title="Tahrirlash" color={C.teal} onClick={() => setModal({ type: "edit", employee: e })} />
                  <IconBtn icon="scan-face" title="Yuz ma'lumoti" color={C.teal} onClick={() => setModal({ type: "face", employee: e })} />
                  <IconBtn icon={e.is_active ? "user-x" : "user-check"} title={e.is_active ? "Faolsizlantirish" : "Faollashtirish"} color={e.is_active ? C.red : C.green} onClick={() => toggleActive(e)} />
                </div>}
              </div>
            ))}
          </StateBox>
        </div>
      </SectionCard>

      {modal && modal.type === "edit" && (
        <EmployeeModal user={user} employee={modal.employee} departments={departments} schedules={schedules} onClose={close} onSaved={refresh}
          onDeleteRequest={(emp) => setModal({ type: "delete", employee: emp })} />
      )}
      {modal && modal.type === "face" && <FaceModal employee={modal.employee} onClose={close} onChanged={refresh} />}
      {modal && modal.type === "delete" && (
        <ConfirmModal
          title="Xodimni butunlay o'chirish" confirmLabel="Butunlay o'chirish" danger onClose={close}
          text={<>
            <b>{modal.employee.full_name}</b> bazadan to'liq o'chiriladi. Uning davomat, vazifa, bonus va intizom tarixi ham o'chib ketadi va qaytarib bo'lmaydi.
            Tarixni saqlab qolish uchun o'chirish o'rniga <b>«Faolsizlantirish»</b> dan foydalaning.
          </>}
          onConfirm={async () => { await api("DELETE", `/api/employees/${modal.employee.id}/?permanent=true`); toast("Xodim o'chirildi"); refresh(); }}
        />
      )}
    </>
  );
}

// =====================================================================
//  Administrator: sozlamalar (klinika joylashuvi, bo'limlar, ish jadvallari)
// =====================================================================
function ClinicSettings() {
  const toast = useContext(ToastCtx);
  const { data, loading, error, reload } = useLoad(() => api("GET", "/api/attendance/location/"), []);
  const [f, setF] = useState(null);
  const [busy, setBusy] = useState(false);
  const [locating, setLocating] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!data) return;
    const l = data.location;
    setF(l ? { ...l, latitude: String(l.latitude), longitude: String(l.longitude) }
      : { name: "Gold Med Clinic", latitude: "", longitude: "", radius_m: 100, max_accuracy_m: 100, check_mode: "either", face_mode: "lenient" });
  }, [data]);

  if (!f) return <SectionCard title="Klinika joylashuvi va davomat qoidalari"><StateBox loading={loading} error={error} onRetry={reload} /></SectionCard>;
  const rt = data.face_runtime;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const useMyLocation = async () => {
    setLocating(true);
    setErr("");
    try {
      const p = await getPosition();
      setF({ ...f, latitude: p.coords.latitude.toFixed(6), longitude: p.coords.longitude.toFixed(6) });
      toast(`Joylashuv olindi (aniqlik ±${Math.round(p.coords.accuracy)} m). «Saqlash» ni bosing.`);
    } catch (e) { setErr(e.message); }
    setLocating(false);
  };

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await api("PUT", "/api/attendance/location/", {
        name: f.name, latitude: f.latitude, longitude: f.longitude,
        radius_m: Number(f.radius_m), max_accuracy_m: Number(f.max_accuracy_m), check_mode: f.check_mode, face_mode: f.face_mode,
      });
      toast("Klinika sozlamalari saqlandi");
      reload();
    } catch (e2) { setErr(e2.message); }
    setBusy(false);
  };

  return (
    <SectionCard title="Klinika joylashuvi va davomat qoidalari" action={<Badge text={data.location ? "Sozlangan" : "Sozlanmagan"} bg={data.location ? C.greenSoft : C.redSoft} fg={data.location ? C.green : C.red} />}>
      <form onSubmit={save} className="px-6 pb-6 flex flex-col gap-4 text-sm">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Kenglik (latitude)"><input className={inputCls} style={inputStyle} value={f.latitude} onChange={set("latitude")} inputMode="decimal" placeholder="41.311081" required /></Field>
          <Field label="Uzunlik (longitude)"><input className={inputCls} style={inputStyle} value={f.longitude} onChange={set("longitude")} inputMode="decimal" placeholder="69.240562" required /></Field>
        </div>
        <div>
          <GhostBtn type="button" onClick={useMyLocation} disabled={locating}>{locating ? "Aniqlanmoqda..." : "Hozirgi joylashuvimni olish"}</GhostBtn>
          <span className="text-xs ml-3" style={{ color: C.muted }}>Klinikada turib bosing yoki Google Maps dan koordinatani nusxalang.</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label="Ruxsat etilgan radius (m)"><input type="number" min="10" max="5000" className={inputCls} style={inputStyle} value={f.radius_m} onChange={set("radius_m")} required /></Field>
          <Field label="Maks. GPS xatosi (m)" hint="Aniqligi bundan past bo'lsa rad etiladi"><input type="number" min="5" className={inputCls} style={inputStyle} value={f.max_accuracy_m} onChange={set("max_accuracy_m")} required /></Field>
          <Field label="Davomat tasdiqlash usuli">
            <select className={inputCls} style={inputStyle} value={f.check_mode} onChange={set("check_mode")}>
              <option value="either">Yuz YOKI joylashuv</option>
              <option value="both">Yuz VA joylashuv</option>
            </select>
          </Field>
        </div>
        <div className="rounded-lg px-3 py-2.5 text-xs flex flex-col gap-1" style={{ background: C.paper, color: C.muted, border: `1px solid ${C.border}` }}>
          {f.check_mode === "either" ? (
            <>
              <span><b>Yuz YOKI joylashuv:</b> xodim klinika radiusida bo'lsa yoki yuzi mos kelsa, davomat qabul qilinadi (bittasi yetarli).</span>
              <span>Diqqat: yuzi mos kelgan xodim klinikadan tashqarida turib ham davomat qila oladi. Bunday yozuvlar davomat jadvalida «Tashqarida» deb ko'rinadi. Yuz ro'yxatdan o'tmagan xodim uchun faqat joylashuv ishlaydi.</span>
            </>
          ) : (
            <span><b>Yuz VA joylashuv:</b> joylashuv klinika radiusida bo'lishi shart; yuzi ro'yxatdan o'tgan xodimning yuzi ham mos kelishi shart.</span>
          )}
        </div>
        {f.check_mode === "both" && (
          <Field label="Yuzni tekshirib bo'lmasa (kutubxona sozlanmagan yoki xodim ro'yxatdan o'tmagan)">
            <select className={inputCls} style={inputStyle} value={f.face_mode} onChange={set("face_mode")}>
              <option value="lenient">Yumshoq: joylashuv bo'yicha qayd etiladi («yuz tekshirilmagan»)</option>
              <option value="strict">Qat'iy: davomat qabul qilinmaydi</option>
            </select>
          </Field>
        )}
        <div className="rounded-lg px-3 py-2.5 flex flex-col gap-1.5" style={{ background: rt.available ? C.tealSoft : C.amberSoft, color: rt.available ? C.teal : C.amber }}>
          <div className="font-semibold flex items-center gap-2"><Icon name={rt.available ? "shield-check" : "info"} size={15} /> Yuz verifikatsiyasi: {rt.available ? "sozlangan va ishlayapti" : "sozlanmagan"}</div>
          {!rt.available && <div className="text-xs">Sozlash uchun README dagi «Yuz verifikatsiyasi» bo'limiga qarang. Sozlanmaguncha davomat yuz tekshirilmasdan, faqat joylashuv bo'yicha yoziladi.</div>}
        </div>
        <ErrorBox text={err} />
        <div className="flex justify-end"><PrimaryBtn type="submit" busy={busy}>Saqlash</PrimaryBtn></div>
      </form>
    </SectionCard>
  );
}

function DepartmentsPanel() {
  const toast = useContext(ToastCtx);
  const { data, loading, error, reload } = useLoad(() => apiAll("/api/departments/"), []);
  const [name, setName] = useState("");
  const [editing, setEditing] = useState(null); // {id, name}
  const [del, setDel] = useState(null);

  const add = async (e) => {
    e.preventDefault();
    try { await api("POST", "/api/departments/", { name: name.trim() }); setName(""); toast("Bo'lim qo'shildi"); reload(); }
    catch (err) { toast(err.message, "error"); }
  };
  const rename = async () => {
    try { await api("PATCH", `/api/departments/${editing.id}/`, { name: editing.name.trim() }); setEditing(null); toast("Bo'lim yangilandi"); reload(); }
    catch (err) { toast(err.message, "error"); }
  };

  return (
    <SectionCard title="Bo'limlar">
      <div className="px-6 pb-6 flex flex-col gap-4">
        <form onSubmit={add} className="flex gap-2">
          <input className={inputCls} style={inputStyle} value={name} onChange={(e) => setName(e.target.value)} placeholder="Yangi bo'lim nomi" required />
          <PrimaryBtn type="submit" icon="plus">Qo'shish</PrimaryBtn>
        </form>
        <StateBox loading={loading && !data} error={error} onRetry={reload} empty={data && data.length === 0 ? "Bo'limlar yo'q." : null}>
          {data && data.map((d) => (
            <div key={d.id} className="flex items-center gap-3 py-2.5" style={{ borderBottom: `1px solid ${C.border}` }}>
              {editing && editing.id === d.id ? (
                <>
                  <input className={inputCls} style={inputStyle} value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} autoFocus />
                  <IconBtn icon="check" title="Saqlash" color={C.green} onClick={rename} />
                  <IconBtn icon="x" title="Bekor qilish" color={C.muted} onClick={() => setEditing(null)} />
                </>
              ) : (
                <>
                  <div style={{ flex: 1, fontSize: 13.5, color: C.text, fontWeight: 500 }}>{d.name}</div>
                  <span style={{ fontSize: 12, color: C.muted }}>{d.employee_count} xodim</span>
                  <IconBtn icon="pencil" title="Tahrirlash" color={C.teal} onClick={() => setEditing({ id: d.id, name: d.name })} />
                  <IconBtn icon="trash-2" title="O'chirish" color={C.red} onClick={() => setDel(d)} />
                </>
              )}
            </div>
          ))}
        </StateBox>
      </div>
      {del && (
        <ConfirmModal title="Bo'limni o'chirish" confirmLabel="O'chirish" danger onClose={() => setDel(null)}
          text={`«${del.name}» bo'limini o'chirmoqchimisiz? Bo'limda xodimlar bo'lsa, o'chirib bo'lmaydi.`}
          onConfirm={async () => { await api("DELETE", `/api/departments/${del.id}/`); toast("Bo'lim o'chirildi"); setDel(null); reload(); }} />
      )}
    </SectionCard>
  );
}

function ScheduleModal({ schedule, onClose, onSaved }) {
  const toast = useContext(ToastCtx);
  const [f, setF] = useState({
    name: schedule ? schedule.name : "", start_time: schedule ? hhmm(schedule.start_time) : "09:00",
    end_time: schedule ? hhmm(schedule.end_time) : "18:00", grace_minutes: schedule ? schedule.grace_minutes : 10,
    days: schedule ? schedule.work_days.split(",").filter((x) => x !== "").map(Number) : [0, 1, 2, 3, 4, 5],
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const toggle = (i) => setF({ ...f, days: f.days.includes(i) ? f.days.filter((d) => d !== i) : [...f.days, i].sort() });

  const submit = async (e) => {
    e.preventDefault();
    if (f.days.length === 0) { setError("Kamida bitta ish kunini tanlang."); return; }
    setBusy(true);
    setError("");
    const body = { name: f.name.trim(), start_time: f.start_time, end_time: f.end_time, grace_minutes: Number(f.grace_minutes), work_days: f.days.join(",") };
    try {
      if (schedule) await api("PATCH", `/api/schedules/${schedule.id}/`, body);
      else await api("POST", "/api/schedules/", body);
      toast("Ish jadvali saqlandi");
      onSaved();
    } catch (err) { setError(err.message); setBusy(false); }
  };

  return (
    <Modal title={schedule ? "Ish jadvalini tahrirlash" : "Yangi ish jadvali"} icon="calendar-clock" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4 text-sm">
        <Field label="Nomi"><input className={inputCls} style={inputStyle} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Masalan: Kunduzgi smena" required /></Field>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Boshlanishi"><input type="time" className={inputCls} style={inputStyle} value={f.start_time} onChange={(e) => setF({ ...f, start_time: e.target.value })} required /></Field>
          <Field label="Tugashi"><input type="time" className={inputCls} style={inputStyle} value={f.end_time} onChange={(e) => setF({ ...f, end_time: e.target.value })} required /></Field>
          <Field label="Imtiyoz (daq.)"><input type="number" min="0" max="120" className={inputCls} style={inputStyle} value={f.grace_minutes} onChange={(e) => setF({ ...f, grace_minutes: e.target.value })} required /></Field>
        </div>
        {f.end_time && f.start_time && f.end_time === f.start_time && (
          <div className="rounded-lg px-3 py-2 text-xs" style={{ background: C.amberSoft, color: C.amber }}>
            Sutkalik smena: boshlanish va tugash vaqti bir xil bo'lgani uchun smena to'liq 24 soat davom etadi
            ({f.start_time} dan ertasi kuni {f.end_time} gacha). Faqat shunday smena kerak bo'lsa saqlang.
          </div>
        )}
        {f.end_time && f.start_time && f.end_time < f.start_time && (
          <div className="rounded-lg px-3 py-2 text-xs" style={{ background: C.tealSoft, color: C.teal }}>
            Tungi smena: ish {f.start_time} da boshlanib, ertasi kuni {f.end_time} da tugaydi. Ish kunlari — smena boshlangan kunlar.
          </div>
        )}
        <Field label="Ish kunlari">
          <div className="flex gap-1.5 flex-wrap">
            {DAY_NAMES.map((n, i) => (
              <button type="button" key={n} onClick={() => toggle(i)} className="rounded-full px-3 py-1.5 text-[12px] font-semibold"
                style={{ background: f.days.includes(i) ? C.ink : C.paper, color: f.days.includes(i) ? "#fff" : C.muted, border: `1px solid ${f.days.includes(i) ? C.ink : C.border}` }}>{n}</button>
            ))}
          </div>
        </Field>
        <ErrorBox text={error} />
        <div className="flex gap-3 justify-end pt-3" style={{ borderTop: `1px solid ${C.border}` }}>
          <GhostBtn type="button" onClick={onClose}>Bekor qilish</GhostBtn>
          <PrimaryBtn type="submit" busy={busy}>Saqlash</PrimaryBtn>
        </div>
      </form>
    </Modal>
  );
}

function SchedulesPanel() {
  const toast = useContext(ToastCtx);
  const { data, loading, error, reload } = useLoad(() => apiAll("/api/schedules/"), []);
  const [modal, setModal] = useState(null); // {schedule}
  const [del, setDel] = useState(null);

  return (
    <SectionCard title="Ish jadvallari" action={
      <button onClick={() => setModal({ schedule: null })} className="flex items-center gap-1.5 rounded-lg px-4 py-2.5 text-white shadow-md active:scale-95 transition-transform" style={{ background: C.ink }}>
        <Icon name="plus" size={14} color="#fff" /><span style={{ fontSize: 12.5, fontWeight: 600 }}>Yangi jadval</span>
      </button>}>
      <div className="px-6 pb-6">
        <StateBox loading={loading && !data} error={error} onRetry={reload} empty={data && data.length === 0 ? "Ish jadvallari yo'q. Kechikish hisoblanishi uchun xodimga jadval biriktiring." : null}>
          {data && data.map((s) => (
            <div key={s.id} className="flex flex-wrap items-center gap-3 py-3" style={{ borderBottom: `1px solid ${C.border}` }}>
              <div style={{ flex: "1 1 200px" }}>
                <div style={{ fontSize: 13.5, color: C.text, fontWeight: 500 }}>{s.name}</div>
                <div style={{ fontSize: 11.5, color: C.muted, marginTop: 3 }}>{hhmm(s.start_time)}–{hhmm(s.end_time)}{hhmm(s.end_time) < hhmm(s.start_time) ? " (ertasi kuni)" : ""} · imtiyoz {s.grace_minutes} daq. · {daysLabel(s.work_days)}</div>
              </div>
              <IconBtn icon="pencil" title="Tahrirlash" color={C.teal} onClick={() => setModal({ schedule: s })} />
              <IconBtn icon="trash-2" title="O'chirish" color={C.red} onClick={() => setDel(s)} />
            </div>
          ))}
        </StateBox>
      </div>
      {modal && <ScheduleModal schedule={modal.schedule} onClose={() => setModal(null)} onSaved={() => { setModal(null); reload(); }} />}
      {del && (
        <ConfirmModal title="Ish jadvalini o'chirish" confirmLabel="O'chirish" danger onClose={() => setDel(null)}
          text={`«${del.name}» jadvalini o'chirmoqchimisiz? Unga biriktirilgan xodimlarda jadval bo'sh qoladi (ular uchun kechikish hisoblanmaydi).`}
          onConfirm={async () => { await api("DELETE", `/api/schedules/${del.id}/`); toast("Ish jadvali o'chirildi"); setDel(null); reload(); }} />
      )}
    </SectionCard>
  );
}

function SettingsView() {
  return (
    <>
      <ClinicSettings />
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-x-6">
        <DepartmentsPanel />
        <SchedulesPanel />
      </div>
    </>
  );
}

// =====================================================================
//  Shaxsiy profil (xodim va administrator uchun)
// =====================================================================
function ProfileView({ user }) {
  const toast = useContext(ToastCtx);
  const [f, setF] = useState({ old_password: "", new_password: "", repeat: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (f.new_password !== f.repeat) { setError("Yangi parollar bir-biriga mos kelmadi."); return; }
    setBusy(true);
    try {
      await api("POST", "/api/auth/change-password/", { old_password: f.old_password, new_password: f.new_password });
      toast("Parol yangilandi");
      setF({ old_password: "", new_password: "", repeat: "" });
    } catch (err) { setError(err.message); }
    setBusy(false);
  };

  const rows = [
    ["F.I.Sh.", user.full_name], ["Login", user.username], ["Lavozim", user.position], ["Bo'lim", user.department || "—"],
    ["Telefon", user.phone || "—"], ["Rol", roleLabel(user)],
  ];

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-x-6">
      <SectionCard title="Shaxsiy ma'lumotlar">
        <div className="px-6 pb-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {rows.map(([k, v]) => <MiniBox key={k} label={k} value={<span style={{ fontSize: 15 }}>{v}</span>} />)}
        </div>
      </SectionCard>
      <SectionCard title="Parolni almashtirish">
        <form onSubmit={submit} className="px-6 pb-6 flex flex-col gap-4 text-sm">
          <Field label="Joriy parol"><input type="password" className={inputCls} style={inputStyle} value={f.old_password} onChange={(e) => setF({ ...f, old_password: e.target.value })} autoComplete="current-password" required /></Field>
          <Field label="Yangi parol" hint="Kamida 8 belgi, oddiy yoki faqat raqamli bo'lmasin"><input type="password" className={inputCls} style={inputStyle} value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} autoComplete="new-password" required /></Field>
          <Field label="Yangi parolni takrorlang"><input type="password" className={inputCls} style={inputStyle} value={f.repeat} onChange={(e) => setF({ ...f, repeat: e.target.value })} autoComplete="new-password" required /></Field>
          <ErrorBox text={error} />
          <div className="flex justify-end"><PrimaryBtn type="submit" busy={busy}>Parolni yangilash</PrimaryBtn></div>
        </form>
      </SectionCard>
    </div>
  );
}

// =====================================================================
//  Umumiy: pul formati, holat uslublari, fayl yuklab olish
// =====================================================================
function money(n) {
  return `${Math.round(Number(n) || 0).toLocaleString("en-US").replace(/,/g, " ")} so'm`;
}

const TASK_STYLE = {
  new: { bg: C.goldSoft, fg: C.gold },
  in_progress: { bg: C.tealSoft, fg: C.teal },
  submitted: { bg: C.amberSoft, fg: C.amber },
  approved: { bg: C.greenSoft, fg: C.green },
  rework: { bg: C.redSoft, fg: C.red },
  overdue: { bg: C.redSoft, fg: C.red },
};
const TASK_FILTERS = [
  ["", "Barchasi"], ["new", "Yangi"], ["in_progress", "Jarayonda"], ["submitted", "Topshirilgan"],
  ["approved", "Tasdiqlangan"], ["rework", "Qayta ishlash"], ["overdue", "Muddati o'tgan"],
];
const KIND_STYLE = {
  warning: { bg: C.amberSoft, fg: C.amber },
  fine: { bg: C.redSoft, fg: C.red },
  reprimand: { bg: C.goldSoft, fg: C.gold },
};

async function downloadFile(url, fallbackName) {
  const res = await fetch(url, { credentials: "same-origin" });
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch (e) { /* JSON emas */ }
    throw new ApiError(res.status, data);
  }
  const cd = res.headers.get("Content-Disposition") || "";
  const m = cd.match(/filename="?([^";]+)"?/);
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = m ? m[1] : fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

function useEmployeeList() {
  return useLoad(() => apiAll("/api/employees/?is_active=true"), []);
}

function FilterChips({ items, value, onChange }) {
  return (
    <div className="flex gap-2 flex-wrap">
      {items.map(([v, label]) => (
        <button
          key={v}
          onClick={() => onChange(v)}
          className="rounded-full px-3.5 py-1.5"
          style={{
            fontSize: 12.5, fontWeight: 600,
            background: value === v ? C.ink : C.paper, color: value === v ? "#fff" : C.muted, border: `1px solid ${value === v ? C.ink : C.border}`,
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

// =====================================================================
//  Topshiriqlar
// =====================================================================
function TaskCreateModal({ onClose, onSaved }) {
  const toast = useContext(ToastCtx);
  const emps = useEmployeeList();
  const depts = useLoad(() => apiAll("/api/departments/"), []);
  const [f, setF] = useState({ title: "", description: "", department: "", start_date: todayISO(), due_date: "" });
  const [picked, setPicked] = useState([]);
  const [filterDept, setFilterDept] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const list = (emps.data || []).filter((e) => !filterDept || String(e.department) === String(filterDept));
  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  const allPicked = list.length > 0 && list.every((e) => picked.includes(e.id));

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (picked.length === 0) { setError("Kamida bitta mas'ul xodimni tanlang."); return; }
    setBusy(true);
    try {
      await api("POST", "/api/tasks/", { ...f, department: f.department || null, assignees: picked });
      toast(`Topshiriq ${picked.length} ta xodimga berildi.`);
      onSaved();
    } catch (err) { setError(err.message); setBusy(false); }
  };

  return (
    <Modal title="Yangi topshiriq" icon="clipboard-list" onClose={onClose} maxWidth="max-w-lg">
      <form onSubmit={submit} className="flex flex-col gap-4 text-sm">
        <Field label="Topshiriq mazmuni"><input required maxLength={255} className={inputCls} style={inputStyle} value={f.title} onChange={set("title")} placeholder="Masalan: Qabulxona jurnalini yangilash" /></Field>
        <Field label="Tavsif (ixtiyoriy)"><textarea rows={3} className={inputCls} style={inputStyle} value={f.description} onChange={set("description")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Boshlanish"><input type="date" required className={inputCls} style={inputStyle} value={f.start_date} onChange={set("start_date")} /></Field>
          <Field label="Muddat"><input type="date" required min={f.start_date} className={inputCls} style={inputStyle} value={f.due_date} onChange={set("due_date")} /></Field>
        </div>
        <Field label="Bo'lim (ixtiyoriy belgi)">
          <select className={inputCls} style={inputStyle} value={f.department} onChange={set("department")}>
            <option value="">—</option>
            {(depts.data || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
        <div>
          <div className="flex items-center justify-between gap-2 mb-1 flex-wrap">
            <label className={labelCls} style={{ marginBottom: 0 }}>Mas'ul xodimlar ({picked.length})</label>
            <div className="flex gap-2 items-center">
              <select className="rounded-lg border px-2 py-1 text-xs" style={inputStyle} value={filterDept} onChange={(e) => setFilterDept(e.target.value)} aria-label="Bo'lim bo'yicha ko'rsatish">
                <option value="">Barcha bo'limlar</option>
                {(depts.data || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
              <button type="button" className="text-xs font-semibold" style={{ color: C.teal }} onClick={() => setPicked(allPicked ? picked.filter((id) => !list.some((e) => e.id === id)) : [...new Set([...picked, ...list.map((e) => e.id)])])}>
                {allPicked ? "Tanlovni olib tashlash" : "Hammasini tanlash"}
              </button>
            </div>
          </div>
          <div className="rounded-lg border max-h-48 overflow-y-auto" style={inputStyle}>
            {emps.loading && <div className="p-3 text-slate-400">Yuklanmoqda...</div>}
            {emps.error && <div className="p-3" style={{ color: C.red }}>{emps.error}</div>}
            {!emps.loading && list.length === 0 && <div className="p-3 text-slate-400">Xodim topilmadi.</div>}
            {list.map((e) => (
              <label key={e.id} className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-slate-50" style={{ borderBottom: `1px solid ${C.border}` }}>
                <input type="checkbox" checked={picked.includes(e.id)} onChange={() => toggle(e.id)} />
                <span className="flex-1">{e.full_name}<span className="text-xs text-slate-500"> · {e.position}</span></span>
              </label>
            ))}
          </div>
        </div>
        <ErrorBox text={error} />
        <div className="flex gap-3 justify-end pt-3" style={{ borderTop: `1px solid ${C.border}` }}>
          <GhostBtn type="button" onClick={onClose}>Bekor qilish</GhostBtn>
          <PrimaryBtn type="submit" busy={busy}>Topshiriq berish</PrimaryBtn>
        </div>
      </form>
    </Modal>
  );
}

function TaskDetailModal({ id, user, mgr, onClose, onChanged }) {
  const canManage = can(user, "tasks.manage");
  const toast = useContext(ToastCtx);
  const { data: t, loading, error, reload } = useLoad(() => api("GET", `/api/tasks/${id}/`), [id]);
  const [comment, setComment] = useState("");
  const [file, setFile] = useState(null);
  const [review, setReview] = useState("");
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [confirmDel, setConfirmDel] = useState(false);
  const [edit, setEdit] = useState(null);

  const run = async (key, fn, okMsg) => {
    setBusy(key);
    setErr("");
    try { await fn(); if (okMsg) toast(okMsg); onChanged(); reload(); } catch (e) { setErr(e.message); }
    setBusy("");
  };

  const open = t && ["new", "in_progress", "rework"].includes(t.status);
  const mine = t && t.employee === user.id;
  const st = t && (TASK_STYLE[t.display_status] || TASK_STYLE.new);
  const subs = t ? t.submissions : [];

  const sendSubmit = () => run("submit", async () => {
    const fd = new FormData();
    fd.append("comment", comment);
    if (file) fd.append("file", file);
    await api("POST", `/api/tasks/${id}/submit/`, fd);
    setComment(""); setFile(null);
  }, "Topshiriq topshirildi.");

  return (
    <Modal title="Topshiriq" icon="clipboard-list" onClose={onClose} maxWidth="max-w-lg">
      <StateBox loading={loading && !t} error={!t && error} onRetry={reload}>
        {t && (
          <div className="flex flex-col gap-4 text-sm">
            <div>
              <div style={{ fontSize: 17, fontWeight: 600, color: C.text }}>{t.title}</div>
              <div className="mt-2 flex gap-2 flex-wrap items-center">
                <Badge text={t.status_label} bg={st.bg} fg={st.fg} />
                <span className="text-slate-500 text-xs">{fmtDate(t.start_date)} → {fmtDate(t.due_date)}</span>
              </div>
            </div>
            {t.description && <div style={{ whiteSpace: "pre-wrap", color: C.text, lineHeight: 1.55 }}>{t.description}</div>}
            <div className="text-xs text-slate-500">
              {mgr && <div>Mas'ul: <b className="text-slate-700">{t.employee_name}</b></div>}
              {t.created_by_name && <div>Bergan: {t.created_by_name}</div>}
            </div>

            {subs.length > 0 && (
              <div className="flex flex-col gap-3">
                <div className={labelCls} style={{ marginBottom: 0 }}>Topshirish tarixi</div>
                {subs.map((s) => (
                  <div key={s.id} className="rounded-xl p-3" style={{ background: C.paper, border: `1px solid ${C.border}` }}>
                    <div className="text-xs text-slate-500 mb-1">{fmtDate(s.submitted_at.slice(0, 10))} {fmtTime(s.submitted_at)}</div>
                    {s.comment && <div style={{ whiteSpace: "pre-wrap" }}>{s.comment}</div>}
                    {s.has_file && (
                      <button className="mt-2 flex items-center gap-1.5 font-semibold" style={{ color: C.teal, fontSize: 13 }}
                        onClick={() => downloadFile(`/api/tasks/files/${s.id}/`, s.file_name).catch((e) => setErr(e.message))}>
                        <Icon name="paperclip" size={14} /> {s.file_name}
                      </button>
                    )}
                    {s.approved !== null && (
                      <div className="mt-2 text-xs" style={{ color: s.approved ? C.green : C.red }}>
                        {s.approved ? "Tasdiqlandi" : "Qayta ishlashga qaytarildi"}{s.reviewed_by_name ? ` · ${s.reviewed_by_name}` : ""}
                        {s.review_comment ? ` — ${s.review_comment}` : ""}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {!mgr && mine && t.status === "rework" && subs[0] && subs[0].review_comment && (
              <ErrorBox text={`Admin izohi: ${subs[0].review_comment}`} />
            )}

            {!mgr && mine && open && (
              <div className="flex flex-col gap-3 pt-3" style={{ borderTop: `1px solid ${C.border}` }}>
                {t.status !== "in_progress" && (
                  <GhostBtn onClick={() => run("start", () => api("POST", `/api/tasks/${id}/start/`), "Topshiriq jarayonga o'tdi.")} disabled={!!busy}>Bajarishni boshlash</GhostBtn>
                )}
                <Field label="Izoh"><textarea rows={3} className={inputCls} style={inputStyle} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Nima qilindi?" /></Field>
                <Field label="Fayl (ixtiyoriy)" hint="PDF, Word, Excel, rasm, txt yoki zip; 10 MB gacha.">
                  <input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.txt,.zip" onChange={(e) => setFile(e.target.files[0] || null)} />
                </Field>
                <PrimaryBtn busy={busy === "submit"} disabled={!comment.trim() && !file} onClick={sendSubmit} icon="send">Topshirish</PrimaryBtn>
              </div>
            )}

            {canManage && mgr && t.status === "submitted" && (
              <div className="flex flex-col gap-3 pt-3" style={{ borderTop: `1px solid ${C.border}` }}>
                <Field label="Izoh (qaytarishda majburiy)"><textarea rows={2} className={inputCls} style={inputStyle} value={review} onChange={(e) => setReview(e.target.value)} /></Field>
                <div className="flex gap-3 flex-wrap">
                  <PrimaryBtn busy={busy === "ok"} icon="check" onClick={() => run("ok", () => api("POST", `/api/tasks/${id}/review/`, { approved: true, comment: review }), "Topshiriq tasdiqlandi.")}>Tasdiqlash</PrimaryBtn>
                  <DangerBtn busy={busy === "no"} onClick={() => run("no", () => api("POST", `/api/tasks/${id}/review/`, { approved: false, comment: review }), "Qayta ishlashga qaytarildi.")}>Qayta ishlashga qaytarish</DangerBtn>
                </div>
              </div>
            )}

            <ErrorBox text={err} />

            {canManage && mgr && (
              <div className="flex gap-3 justify-between pt-3" style={{ borderTop: `1px solid ${C.border}` }}>
                <IconBtn icon="pencil" title="Tahrirlash" color={C.teal} onClick={() => setEdit({ title: t.title, description: t.description, due_date: t.due_date })} />
                <IconBtn icon="trash-2" title="O'chirish" color={C.red} onClick={() => setConfirmDel(true)} />
              </div>
            )}
          </div>
        )}
      </StateBox>

      {edit && (
        <Modal title="Topshiriqni tahrirlash" icon="pencil" onClose={() => setEdit(null)}>
          <div className="flex flex-col gap-4 text-sm">
            <Field label="Mazmuni"><input className={inputCls} style={inputStyle} value={edit.title} onChange={(e) => setEdit({ ...edit, title: e.target.value })} /></Field>
            <Field label="Tavsif"><textarea rows={3} className={inputCls} style={inputStyle} value={edit.description} onChange={(e) => setEdit({ ...edit, description: e.target.value })} /></Field>
            <Field label="Muddat"><input type="date" className={inputCls} style={inputStyle} value={edit.due_date} onChange={(e) => setEdit({ ...edit, due_date: e.target.value })} /></Field>
            <div className="flex gap-3 justify-end pt-3" style={{ borderTop: `1px solid ${C.border}` }}>
              <GhostBtn onClick={() => setEdit(null)}>Bekor qilish</GhostBtn>
              <PrimaryBtn busy={busy === "edit"} onClick={() => run("edit", async () => { await api("PATCH", `/api/tasks/${id}/`, edit); setEdit(null); }, "Topshiriq yangilandi.")}>Saqlash</PrimaryBtn>
            </div>
          </div>
        </Modal>
      )}
      {confirmDel && (
        <ConfirmModal
          title="Topshiriqni o'chirish" danger confirmLabel="O'chirish"
          text="Topshiriq barcha biriktirilgan xodimlardan va topshirilgan javoblari bilan birga o'chadi. Davom etasizmi?"
          onClose={() => setConfirmDel(false)}
          onConfirm={async () => { await api("DELETE", `/api/tasks/${id}/`); toast("Topshiriq o'chirildi."); onChanged(); onClose(); }}
        />
      )}
    </Modal>
  );
}

function TasksView({ user, search, onChanged, mgr }) {
  const isAdmin = !!mgr;
  const canManage = can(user, "tasks.manage");
  const [status, setStatus] = useState("");
  const [dept, setDept] = useState("");
  const [page, setPage] = useState(1);
  const [create, setCreate] = useState(false);
  const [openId, setOpenId] = useState(null);
  const q = useDebounced(search);
  useEffect(() => { setPage(1); }, [status, dept, q]);

  const depts = useLoad(() => (isAdmin ? apiAll("/api/departments/") : Promise.resolve([])), []);
  const { data, loading, error, reload } = useLoad(() => api("GET", "/api/tasks/" + qs({ scope: isAdmin ? "all" : "", status, department: dept, search: q, page })), [status, dept, q, page]);
  const rows = data ? data.results : [];
  const refresh = () => { reload(); onChanged && onChanged(); };

  return (
    <>
      <SectionCard
        title={isAdmin ? "Topshiriqlar" : "Mening topshiriqlarim"}
        action={canManage && isAdmin && <PrimaryBtn icon="plus" onClick={() => setCreate(true)}>Yangi topshiriq</PrimaryBtn>}
      >
        <div className="px-6 pb-4 flex flex-col gap-3">
          <FilterChips items={TASK_FILTERS} value={status} onChange={setStatus} />
          {isAdmin && (
            <div className="max-w-xs">
              <Field label="Bo'lim">
                <select className={inputCls} style={inputStyle} value={dept} onChange={(e) => setDept(e.target.value)}>
                  <option value="">Barchasi</option>
                  {(depts.data || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </Field>
            </div>
          )}
        </div>
        <StateBox loading={loading && !data} error={error} onRetry={reload} empty={data && rows.length === 0 ? (isAdmin ? "Topshiriqlar topilmadi." : "Sizga hozircha topshiriq berilmagan.") : null}>
          {data && rows.length > 0 && (
            <div className="px-6 pb-5 flex flex-col gap-2">
              {rows.map((t) => {
                const s = TASK_STYLE[t.display_status] || TASK_STYLE.new;
                return (
                  <button key={t.id} onClick={() => setOpenId(t.id)} className="flex items-center justify-between gap-3 rounded-xl px-4 py-3 text-left hover:shadow-sm transition-shadow w-full" style={{ border: `1px solid ${C.border}`, background: C.card }}>
                    <div className="min-w-0">
                      <div className="truncate" style={{ fontSize: 14, fontWeight: 600, color: C.text }}>{t.title}</div>
                      <div className="text-xs text-slate-500 mt-0.5 truncate">
                        {isAdmin && <>{t.employee_name} · </>}Muddat: {fmtDate(t.due_date)}
                      </div>
                    </div>
                    <Badge text={t.status_label} bg={s.bg} fg={s.fg} />
                  </button>
                );
              })}
            </div>
          )}
        </StateBox>
        {data && <Pager page={page} count={data.count} onPage={setPage} />}
      </SectionCard>
      {create && <TaskCreateModal onClose={() => setCreate(false)} onSaved={() => { setCreate(false); setPage(1); refresh(); }} />}
      {openId && <TaskDetailModal id={openId} user={user} mgr={isAdmin} onClose={() => setOpenId(null)} onChanged={refresh} />}
    </>
  );
}

// =====================================================================
//  Bonus va Ogohlantirish/Jarima (bitta umumiy ko'rinish)
// =====================================================================
const KIND_OPTIONS = [["warning", "Ogohlantirish"], ["fine", "Jarima"], ["reprimand", "Hayfsan"]];

function RewardModal({ mode, item, onClose, onSaved }) {
  const toast = useContext(ToastCtx);
  const isBonus = mode === "bonus";
  const emps = useEmployeeList();
  const [f, setF] = useState(item
    ? { employee: item.employee, amount: item.amount, reason: item.reason, date: item.date, kind: item.kind || "warning", note: item.note || "" }
    : { employee: "", amount: "", reason: "", date: todayISO(), kind: "warning", note: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const needAmount = isBonus || f.kind === "fine";

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const body = { employee: f.employee, reason: f.reason, date: f.date };
    if (isBonus) body.amount = f.amount;
    else { body.kind = f.kind; body.note = f.note; body.amount = needAmount ? f.amount : 0; }
    try {
      await api(item ? "PATCH" : "POST", `/api/${isBonus ? "bonuses" : "discipline"}/${item ? item.id + "/" : ""}`, body);
      toast(item ? "Yozuv yangilandi." : "Yozuv qo'shildi.");
      onSaved();
    } catch (err) { setError(err.message); setBusy(false); }
  };

  return (
    <Modal title={(item ? "Tahrirlash: " : "Yangi: ") + (isBonus ? "bonus" : "ogohlantirish / jarima")} icon={isBonus ? "gift" : "triangle-alert"} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4 text-sm">
        <Field label="Xodim">
          <select required disabled={!!item} className={inputCls} style={inputStyle} value={f.employee} onChange={set("employee")}>
            <option value="">Tanlang...</option>
            {(item && !(emps.data || []).some((e) => e.id === item.employee) ? [{ id: item.employee, full_name: item.employee_name }] : []).concat(emps.data || []).map((e) => <option key={e.id} value={e.id}>{e.full_name}</option>)}
          </select>
        </Field>
        {!isBonus && (
          <Field label="Turi">
            <select className={inputCls} style={inputStyle} value={f.kind} onChange={set("kind")}>
              {KIND_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
        )}
        {needAmount && <Field label="Summa (so'm)"><input required type="number" min="1" step="1" className={inputCls} style={inputStyle} value={f.amount} onChange={set("amount")} /></Field>}
        <Field label="Sabab"><input required maxLength={255} className={inputCls} style={inputStyle} value={f.reason} onChange={set("reason")} /></Field>
        {!isBonus && <Field label="Izoh (ixtiyoriy)"><textarea rows={2} className={inputCls} style={inputStyle} value={f.note} onChange={set("note")} /></Field>}
        <Field label="Sana"><input required type="date" max={todayISO()} className={inputCls} style={inputStyle} value={f.date} onChange={set("date")} /></Field>
        <ErrorBox text={error} />
        <div className="flex gap-3 justify-end pt-3" style={{ borderTop: `1px solid ${C.border}` }}>
          <GhostBtn type="button" onClick={onClose}>Bekor qilish</GhostBtn>
          <PrimaryBtn type="submit" busy={busy}>Saqlash</PrimaryBtn>
        </div>
      </form>
    </Modal>
  );
}

function RewardsView({ user, search, mode, mgr }) {
  const isAdmin = !!mgr;
  const isBonus = mode === "bonus";
  const canManage = can(user, isBonus ? "bonuses.manage" : "discipline.manage");
  const base = isBonus ? "/api/bonuses/" : "/api/discipline/";
  const toast = useContext(ToastCtx);
  const [from, setFrom] = useState(weekAgoISO());
  const [to, setTo] = useState(todayISO());
  const [dept, setDept] = useState("");
  const [kind, setKind] = useState("");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState(null); // {item?}
  const [cancel, setCancel] = useState(null);
  const q = useDebounced(search);
  useEffect(() => { setPage(1); }, [from, to, dept, kind, q]);

  const depts = useLoad(() => (isAdmin ? apiAll("/api/departments/") : Promise.resolve([])), []);
  const { data, loading, error, reload } = useLoad(
    () => api("GET", base + qs({ scope: isAdmin ? "all" : "", date_from: from, date_to: to, department: dept, kind, search: q, page })),
    [from, to, dept, kind, q, page, mode]
  );
  const rows = data ? data.results : [];
  const heads = [...(isAdmin ? ["Xodim"] : []), "Sana", ...(isBonus ? [] : ["Turi"]), "Sabab", "Summa", ...(canManage && isAdmin ? [""] : [])];

  return (
    <>
      <SectionCard
        title={isBonus ? (isAdmin ? "Bonuslar" : "Mening bonuslarim") : (isAdmin ? "Ogohlantirish va jarimalar" : "Mening ogohlantirish va jarimalarim")}
        action={canManage && isAdmin && <PrimaryBtn icon="plus" onClick={() => setModal({})}>Qo'shish</PrimaryBtn>}
      >
        <div className="px-6 pb-4 grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
          <Field label="Sanadan"><input type="date" className={inputCls} style={inputStyle} value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
          <Field label="Sanagacha"><input type="date" className={inputCls} style={inputStyle} value={to} onChange={(e) => setTo(e.target.value)} /></Field>
          {isAdmin && (
            <Field label="Bo'lim">
              <select className={inputCls} style={inputStyle} value={dept} onChange={(e) => setDept(e.target.value)}>
                <option value="">Barchasi</option>
                {(depts.data || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </Field>
          )}
          {!isBonus && (
            <Field label="Turi">
              <select className={inputCls} style={inputStyle} value={kind} onChange={(e) => setKind(e.target.value)}>
                <option value="">Barchasi</option>
                {KIND_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Field>
          )}
        </div>
        <StateBox loading={loading && !data} error={error} onRetry={reload} empty={data && rows.length === 0 ? "Yozuvlar topilmadi." : null}>
          {data && rows.length > 0 && (
            <div className="px-6 pb-5 overflow-x-auto">
              <table className="w-full text-left" style={{ borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                    {heads.map((h, i) => <th key={i} className="pb-3 pt-1 pr-4 text-slate-500 font-semibold uppercase text-[11px] tracking-wider whitespace-nowrap">{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                      {isAdmin && (
                        <td className="py-3.5 pr-4 text-[13px]">
                          <div className="font-medium text-slate-800">{r.employee_name}</div>
                          <div className="text-[11.5px] text-slate-500">{r.department || "—"}</div>
                        </td>
                      )}
                      <td className="py-3.5 pr-4 text-[12.5px] whitespace-nowrap">{fmtDate(r.date)}</td>
                      {!isBonus && <td className="py-3.5 pr-4"><Badge text={r.kind_label} bg={KIND_STYLE[r.kind].bg} fg={KIND_STYLE[r.kind].fg} /></td>}
                      <td className="py-3.5 pr-4 text-[13px] text-slate-700">{r.reason}{r.note ? <div className="text-[11.5px] text-slate-500">{r.note}</div> : null}</td>
                      <td className="py-3.5 pr-4 text-[13px] font-semibold whitespace-nowrap" style={{ color: isBonus ? C.green : Number(r.amount) ? C.red : C.muted }}>
                        {isBonus || Number(r.amount) ? money(r.amount) : "—"}
                      </td>
                      {canManage && isAdmin && (
                        <td className="py-3.5 whitespace-nowrap">
                          <button className="p-1.5 rounded-lg hover:bg-slate-100" title="Tahrirlash" aria-label="Tahrirlash" onClick={() => setModal({ item: r })}><Icon name="pencil" size={15} color={C.muted} /></button>
                          <button className="p-1.5 rounded-lg hover:bg-slate-100" title="Bekor qilish" aria-label="Bekor qilish" onClick={() => setCancel(r)}><Icon name="ban" size={15} color={C.red} /></button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </StateBox>
        {data && <Pager page={page} count={data.count} onPage={setPage} />}
      </SectionCard>
      {modal && <RewardModal mode={mode} item={modal.item} onClose={() => setModal(null)} onSaved={() => { setModal(null); reload(); }} />}
      {cancel && (
        <ConfirmModal
          title="Yozuvni bekor qilish" danger confirmLabel="Bekor qilish"
          text={`«${cancel.reason}» (${cancel.employee_name}) yozuvi bekor qilinadi va xodimga ko'rinmaydi. Tarix saqlanadi.`}
          onClose={() => setCancel(null)}
          onConfirm={async () => { await api("POST", `${base}${cancel.id}/cancel/`); toast("Yozuv bekor qilindi."); setCancel(null); reload(); }}
        />
      )}
    </>
  );
}

// =====================================================================
//  Hisobotlar (ko'rish + PDF/Excel)
// =====================================================================
const REPORT_TABS = [["attendance", "Davomat"], ["tasks", "Topshiriqlar"], ["bonuses", "Bonuslar"], ["discipline", "Ogohlantirish/Jarima"]];
const REPORT_BADGE = {
  "O'z vaqtida": ATT_STYLE.on_time, "Kechikdi": ATT_STYLE.late, "Kelmadi": ATT_STYLE.absent,
  "Yangi": TASK_STYLE.new, "Jarayonda": TASK_STYLE.in_progress, "Topshirilgan": TASK_STYLE.submitted,
  "Tasdiqlangan": TASK_STYLE.approved, "Qayta ishlash kerak": TASK_STYLE.rework, "Muddati o'tgan": TASK_STYLE.overdue,
};

function ReportsView() {
  const toast = useContext(ToastCtx);
  const [kind, setKind] = useState("attendance");
  const [from, setFrom] = useState(weekAgoISO());
  const [to, setTo] = useState(todayISO());
  const [emp, setEmp] = useState("");
  const [dept, setDept] = useState("");
  const [position, setPosition] = useState("");
  const [status, setStatus] = useState("");
  const [dkind, setDkind] = useState("");
  const [page, setPage] = useState(1);
  const [exporting, setExporting] = useState("");
  const pos = useDebounced(position);
  useEffect(() => { setPage(1); }, [kind, from, to, emp, dept, pos, status, dkind]);
  useEffect(() => { setStatus(""); setDkind(""); }, [kind]);

  const emps = useEmployeeList();
  const depts = useLoad(() => apiAll("/api/departments/"), []);
  const params = { date_from: from, date_to: to, employee: emp, department: dept, position: pos, status: kind === "attendance" || kind === "tasks" ? status : "", kind: kind === "discipline" ? dkind : "" };
  const { data, loading, error, reload } = useLoad(() => api("GET", `/api/reports/${kind}/` + qs({ ...params, page })), [kind, from, to, emp, dept, pos, status, dkind, page]);

  const doExport = async (fmt) => {
    setExporting(fmt);
    try { await downloadFile(`/api/reports/${kind}/` + qs({ ...params, export: fmt }), `hisobot.${fmt}`); toast(fmt === "pdf" ? "PDF yuklab olindi." : "Excel yuklab olindi."); }
    catch (e) { toast(e.message, "error"); }
    setExporting("");
  };

  const statusOptions = kind === "attendance"
    ? [["on_time", "O'z vaqtida"], ["late", "Kechikdi"], ["absent", "Kelmadi"]]
    : kind === "tasks" ? TASK_FILTERS.slice(1) : null;

  return (
    <SectionCard
      title="Hisobotlar"
      action={
        <div className="flex gap-2">
          <GhostBtn disabled={!!exporting || !data} onClick={() => doExport("xlsx")}>{exporting === "xlsx" ? "Kuting..." : "Excel"}</GhostBtn>
          <GhostBtn disabled={!!exporting || !data} onClick={() => doExport("pdf")}>{exporting === "pdf" ? "Kuting..." : "PDF"}</GhostBtn>
        </div>
      }
    >
      <div className="px-6 pb-4 flex flex-col gap-4">
        <FilterChips items={REPORT_TABS} value={kind} onChange={setKind} />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
          <Field label="Sanadan"><input type="date" className={inputCls} style={inputStyle} value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
          <Field label="Sanagacha"><input type="date" className={inputCls} style={inputStyle} value={to} onChange={(e) => setTo(e.target.value)} /></Field>
          <Field label="Xodim">
            <select className={inputCls} style={inputStyle} value={emp} onChange={(e) => setEmp(e.target.value)}>
              <option value="">Barchasi</option>
              {(emps.data || []).map((e) => <option key={e.id} value={e.id}>{e.full_name}</option>)}
            </select>
          </Field>
          <Field label="Bo'lim">
            <select className={inputCls} style={inputStyle} value={dept} onChange={(e) => setDept(e.target.value)}>
              <option value="">Barchasi</option>
              {(depts.data || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
          <Field label="Lavozim"><input className={inputCls} style={inputStyle} value={position} onChange={(e) => setPosition(e.target.value)} placeholder="Masalan: hamshira" /></Field>
          {statusOptions && (
            <Field label="Holat">
              <select className={inputCls} style={inputStyle} value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">Barchasi</option>
                {statusOptions.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Field>
          )}
          {kind === "discipline" && (
            <Field label="Turi">
              <select className={inputCls} style={inputStyle} value={dkind} onChange={(e) => setDkind(e.target.value)}>
                <option value="">Barchasi</option>
                {KIND_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Field>
          )}
        </div>
      </div>
      <StateBox loading={loading && !data} error={error} onRetry={reload}>
        {data && (
          <>
            <div className="px-6 pb-4 flex gap-2 flex-wrap">
              {Object.entries(data.summary).map(([k, v]) => (
                <span key={k} className="rounded-full px-3 py-1" style={{ background: C.paper, border: `1px solid ${C.border}`, fontSize: 12.5, color: C.text }}>
                  {k}: <b>{v}</b>
                </span>
              ))}
            </div>
            {data.results.length === 0 ? (
              <div className="text-center py-8 text-slate-400 text-sm">Tanlangan filtrlar bo'yicha ma'lumot topilmadi.</div>
            ) : (
              <div className="px-6 pb-5 overflow-x-auto">
                <table className="w-full text-left" style={{ borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                      {data.columns.map((c) => <th key={c.key} className="pb-3 pt-1 pr-4 text-slate-500 font-semibold uppercase text-[11px] tracking-wider whitespace-nowrap">{c.label}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((r, i) => (
                      <tr key={i} style={{ borderBottom: `1px solid ${C.border}` }}>
                        {data.columns.map((c) => {
                          const b = c.key === "status" ? REPORT_BADGE[r.status] : null;
                          return <td key={c.key} className="py-3 pr-4 text-[12.5px] text-slate-700">{b ? <Badge text={r.status} bg={b.bg} fg={b.fg} /> : r[c.key]}</td>;
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Pager page={page} count={data.count} size={data.page_size} onPage={setPage} />
          </>
        )}
      </StateBox>
    </SectionCard>
  );
}

// =====================================================================
//  Bildirishnomalar (qo'ng'iroqcha)
// =====================================================================
function NotificationBell({ onNavigate }) {
  const [open, setOpen] = useState(false);
  const { data, reload } = useLoad(() => api("GET", "/api/notifications/"), []);
  const wrap = useRef(null);
  useEffect(() => {
    const t = setInterval(reload, 60000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    if (!open) return;
    reload();
    const h = (e) => wrap.current && !wrap.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);

  const unread = data ? data.unread : 0;
  const items = data ? data.results : [];
  const click = async (n) => {
    try { if (!n.is_read) await api("POST", `/api/notifications/${n.id}/read/`); } catch (e) { /* e'tiborsiz */ }
    setOpen(false);
    reload();
    if (n.link) onNavigate(n.link.replace(/^[#/]+/, ""));
  };
  const readAll = async () => { try { await api("POST", "/api/notifications/read-all/"); } catch (e) { /* e'tiborsiz */ } reload(); };

  return (
    <div className="relative" ref={wrap}>
      <button onClick={() => setOpen(!open)} aria-label="Bildirishnomalar" className="relative rounded-full p-2.5" style={{ background: C.paper, border: `1px solid ${C.border}` }}>
        <Icon name="bell" size={17} color={C.text} />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 rounded-full flex items-center justify-center text-white" style={{ background: C.red, fontSize: 10, fontWeight: 700, minWidth: 18, height: 18, padding: "0 4px" }}>{unread > 99 ? "99+" : unread}</span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 rounded-2xl shadow-xl z-50 overflow-hidden" style={{ width: "min(360px, calc(100vw - 32px))", background: C.card, border: `1px solid ${C.border}` }}>
          <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: `1px solid ${C.border}` }}>
            <b style={{ fontSize: 14 }}>Bildirishnomalar</b>
            {unread > 0 && <button className="text-xs font-semibold" style={{ color: C.teal }} onClick={readAll}>Hammasini o'qilgan deb belgilash</button>}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 && <div className="text-center text-sm text-slate-400 py-8">Bildirishnomalar yo'q.</div>}
            {items.map((n) => (
              <button key={n.id} onClick={() => click(n)} className="w-full text-left px-4 py-3 hover:bg-slate-50 flex gap-3" style={{ borderBottom: `1px solid ${C.border}`, background: n.is_read ? "transparent" : C.goldSoft + "88" }}>
                <div className="rounded-full flex-shrink-0 w-2 h-2 mt-1.5" style={{ background: n.is_read ? "transparent" : C.gold }} />
                <div className="min-w-0">
                  <div style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{n.title}</div>
                  {n.body && <div className="text-xs text-slate-600 mt-0.5" style={{ wordBreak: "break-word" }}>{n.body}</div>}
                  <div className="text-[11px] text-slate-400 mt-1">{relTime(n.created_at)}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Xodim bosh sahifasi: topshiriq / bonus / intizom qisqa ko'rsatkichlari
function EmployeeSummary({ onNavigate }) {
  const { data } = useLoad(() => api("GET", "/api/reports/summary/"), []);
  if (!data) return null;
  const Box = ({ label, value, color, to }) => (
    <button onClick={() => onNavigate(to)} className="rounded-xl p-4 text-left hover:shadow-sm" style={{ border: `1px solid ${C.border}`, background: C.card }}>
      <div style={{ fontSize: 11.5, color: C.muted, textTransform: "uppercase", letterSpacing: 0.8, fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 22, color, fontWeight: 600, marginTop: 6 }}>{value}</div>
    </button>
  );
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-5">
      <Box label="Ochiq topshiriqlar" value={data.open_tasks} color={C.teal} to="tasks" />
      <Box label="Muddati o'tgan" value={data.overdue_tasks} color={data.overdue_tasks ? C.red : C.text} to="tasks" />
      <Box label="Bonus (shu oy)" value={money(data.bonus_sum_month)} color={C.green} to="bonuses" />
      <Box label="Ogohlantirish/jarima (shu oy)" value={data.discipline_count_month} color={data.discipline_count_month ? C.red : C.text} to="warnings" />
    </div>
  );
}

// =====================================================================
//  Asosiy ilova
// =====================================================================
const ADMIN_NAV = [
  { id: "dashboard", label: "Boshqaruv paneli", icon: "layout-dashboard" },
  { id: "tasks", label: "Topshiriqlar", icon: "clipboard-list" },
  { id: "warnings", label: "Ogohlantirish/Jarima", icon: "triangle-alert" },
  { id: "bonuses", label: "Bonus", icon: "gift" },
  { id: "employees", label: "Xodimlar", icon: "users" },
  { id: "attendance", label: "Davomat", icon: "calendar-check" },
  { id: "reports", label: "Hisobotlar", icon: "file-text" },
];
const ADMIN_BOTTOM = { id: "settings", label: "Sozlamalar", icon: "settings" };
const EMP_NAV = [
  { id: "home", label: "Bosh sahifa", icon: "layout-dashboard" },
  { id: "tasks", label: "Topshiriqlarim", icon: "clipboard-list" },
  { id: "attendance", label: "Davomat tarixi", icon: "calendar-check" },
  { id: "bonuses", label: "Bonuslarim", icon: "gift" },
  { id: "warnings", label: "Ogohlantirishlarim", icon: "triangle-alert" },
];
const EMP_BOTTOM = { id: "profile", label: "Profil", icon: "user" };
// Ruxsati bor oddiy xodimlar uchun qo'shimcha boshqaruv menyulari (id "m-" bilan boshlanadi)
const MGR_NAV = [
  { id: "m-dashboard", label: "Boshqaruv paneli", icon: "layout-dashboard", perm: "dashboard.view" },
  { id: "m-tasks", label: "Barcha topshiriqlar", icon: "clipboard-list", perm: "tasks.view" },
  { id: "m-warnings", label: "Ogohlantirish/Jarima", icon: "triangle-alert", perm: "discipline.view" },
  { id: "m-bonuses", label: "Bonuslar", icon: "gift", perm: "bonuses.view" },
  { id: "m-employees", label: "Xodimlar", icon: "users", perm: "employees.view" },
  { id: "m-attendance", label: "Barcha davomat", icon: "calendar-check", perm: "attendance.view" },
  { id: "m-reports", label: "Hisobotlar", icon: "file-text", perm: "reports.view" },
  { id: "m-settings", label: "Sozlamalar", icon: "settings", perm: "settings.manage" },
];
// Sahifa manzili: "tasks" -> /tasks, "m-tasks" -> /manage/tasks, "home" -> /
const idToPath = (id) => (id === "home" ? "/" : id.startsWith("m-") ? "/manage/" + id.slice(2) : "/" + id);
const pathToId = (path) => {
  const p = path.replace(/^\/+|\/+$/g, "");
  if (!p) return "home";
  return p.startsWith("manage/") ? "m-" + p.slice(7) : p;
};
const SEARCHABLE = ["employees", "attendance", "tasks", "warnings", "bonuses"];

function Shell({ user, onLogout }) {
  const summary = useLoad(() => api("GET", "/api/reports/summary/"), []);
  useEffect(() => {
    const t = setInterval(summary.reload, 60000);
    return () => clearInterval(t);
  }, []);
  const isAdmin = !!user.is_admin;
  const badgeFor = (id) => {
    if (!summary.data) return 0;
    if (id === "tasks") return isAdmin ? summary.data.tasks_to_review : summary.data.open_tasks;
    if (id === "m-tasks") return summary.data.tasks_to_review || 0;
    return 0;
  };
  const mgrItems = isAdmin ? [] : MGR_NAV.filter((n) => can(user, n.perm));
  const nav = [
    ...(isAdmin ? ADMIN_NAV : EMP_NAV),
    ...(mgrItems.length ? [{ heading: "Boshqaruv" }, ...mgrItems] : []),
  ].map((n) => ({ ...n, badge: n.id ? badgeFor(n.id) : 0 }));
  const bottom = isAdmin ? ADMIN_BOTTOM : EMP_BOTTOM;
  const items = nav.filter((n) => n.id);
  const all = [...items, bottom];
  const idFromUrl = () => {
    const legacy = window.location.hash.replace(/^#\/?/, ""); // eski "#tasks" havolalari ham ishlaydi
    const id = legacy || pathToId(window.location.pathname);
    return all.some((n) => n.id === id) ? id : items[0].id;
  };
  const [active, setActiveRaw] = useState(idFromUrl);
  useEffect(() => {
    const onPop = () => { setActiveRaw(idFromUrl()); setSearch(""); setMenuOpen(false); };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const [menuOpen, setMenuOpen] = useState(false);
  const [search, setSearch] = useState("");
  const dashDate = useLoad(() => (can(user, "dashboard.view") ? api("GET", "/api/reports/dashboard/") : Promise.resolve(null)), []);

  const setActive = (id) => {
    setActiveRaw(id);
    setSearch("");
    setMenuOpen(false);
    const path = idToPath(id);
    if (window.location.pathname !== path || window.location.hash) window.history.pushState(null, "", path);
  };

  const current = all.find((n) => n.id === active) || items[0];
  const baseId = active.replace(/^m-/, "");
  const subtitle = baseId === "dashboard" && active !== "home" && dashDate.data ? `Gold Med Clinic — bugungi ish holati, ${fmtLongDate(dashDate.data.date)}` : undefined;

  const views = {
    dashboard: <Dashboard onNavigate={setActive} />,
    tasks: <TasksView user={user} mgr={isAdmin} search={search} onChanged={summary.reload} />,
    warnings: <RewardsView key="warnings" user={user} mgr={isAdmin} search={search} mode="discipline" />,
    bonuses: <RewardsView key="bonuses" user={user} mgr={isAdmin} search={search} mode="bonus" />,
    reports: <ReportsView />,
    employees: <EmployeesView user={user} search={search} />,
    attendance: <AttendanceView user={user} mgr={isAdmin} search={search} />,
    settings: <SettingsView />,
    home: <EmployeeHome user={user} onNavigate={setActive} />,
    profile: <ProfileView user={user} />,
    "m-dashboard": <Dashboard onNavigate={(id) => setActive(MGR_NAV.some((n) => n.id === "m-" + id) ? "m-" + id : id)} />,
    "m-tasks": <TasksView key="m-tasks" user={user} mgr search={search} onChanged={summary.reload} />,
    "m-warnings": <RewardsView key="m-warnings" user={user} mgr search={search} mode="discipline" />,
    "m-bonuses": <RewardsView key="m-bonuses" user={user} mgr search={search} mode="bonus" />,
    "m-reports": <ReportsView />,
    "m-employees": <EmployeesView user={user} search={search} />,
    "m-attendance": <AttendanceView key="m-attendance" user={user} mgr search={search} />,
    "m-settings": <SettingsView />,
  };

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: C.paper }}>
      {menuOpen && <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={() => setMenuOpen(false)} />}
      <div className={`fixed inset-y-0 left-0 z-40 transform transition-transform md:static md:translate-x-0 md:z-auto ${menuOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <Sidebar nav={nav} bottom={bottom} active={active} setActive={setActive} user={user} onLogout={onLogout} />
      </div>

      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <TopBar
          title={current.label}
          subtitle={subtitle}
          onMenu={() => setMenuOpen(true)}
          search={search}
          setSearch={(isAdmin || active.startsWith("m-")) && SEARCHABLE.includes(baseId) ? setSearch : undefined}
          bell={<NotificationBell onNavigate={(id) => all.some((n) => n.id === id) && setActive(id)} />}
        />
        <div className="flex-1 overflow-auto p-4 md:p-8">
          <div className="flex items-center gap-1.5 mb-5 text-slate-500 text-xs">
            <span>Boshqaruv</span>
            <Icon name="chevron-right" size={11} />
            <span className="font-semibold text-slate-800">{current.label}</span>
          </div>
          {views[current.id]}
        </div>
      </div>
    </div>
  );
}

function App() {
  const boot = JSON.parse(document.getElementById("boot-data").textContent);
  const [user, setUser] = useState(boot);

  useEffect(() => { onUnauthorized = () => setUser(null); }, []);

  const logout = async () => {
    try { await api("POST", "/api/auth/logout/"); } catch (e) { /* baribir chiqamiz */ }
    window.history.replaceState(null, "", "/");
    setUser(null);
  };

  if (!user) return <Login onLoggedIn={setUser} />;
  return <Shell key={user.id} user={user} onLogout={logout} />;
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<ToastHost><App /></ToastHost>);
