import { useEffect, useRef, useState } from "react";
import MIcon from "../../../components/MIcon";
import {
  useTheme,
  THEME_OPTIONS,
  STYLE_OPTIONS,
  BACKGROUND_OPTIONS,
  THEME_DEFAULTS,
} from "../../../contexts/ThemeContext";
import { useToast } from "../../../hooks/useToast";
import { downscaleImage } from "../../../utils/image/downscaleImage";
import { normalizeHex } from "../../../utils/theme/derivePrimaryShades";
import styles from "./AccountSettingsPage.module.scss";

/** 背景圖 data URL 上限：留在 localStorage 配額（約 5MB）內 */
const BG_IMAGE_MAX_CHARS = 3 * 1024 * 1024;

/* ── 外觀 ───────────────────────────────────────────── */

/** 未自訂時玻璃質感「跟隨主色」實際呈現的是原始三色暈染，縮圖同步顯示 */
const CLASSIC_PREVIEW =
  "linear-gradient(135deg, var(--color-bg-gradient-blue), var(--color-bg-gradient-yellow) 55%, var(--color-bg-gradient-green))";

/** 可直接輸入 HEX 色碼的欄位，失焦或 Enter 時套用（無效輸入還原） */
function HexInput({ value, onChange, ariaLabel }) {
  const [draft, setDraft] = useState(value);
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (!focused) setDraft(value);
  }, [value, focused]);

  function commit() {
    try {
      onChange(normalizeHex(draft));
    } catch {
      setDraft(value);
    }
  }

  return (
    <input
      type="text"
      className={styles.hexInput}
      value={draft}
      onFocus={() => setFocused(true)}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        setFocused(false);
        commit();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") commit();
      }}
      maxLength={7}
      spellCheck={false}
      aria-label={ariaLabel}
    />
  );
}

function OptionGroup({ label, options, value, onSelect }) {
  return (
    <div className={styles.field}>
      <span>{label}</span>
      <div className={styles.optionRow}>
        {options.map((opt) => (
          <button
            key={opt.key}
            type="button"
            className={value === opt.key ? styles.optionBtnActive : styles.optionBtn}
            onClick={() => onSelect(opt.key)}
          >
            <MIcon name={opt.icon} size={16} />
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function AppearanceTab() {
  const {
    theme,
    mode,
    setMode,
    primaryColor,
    setPrimaryColor,
    style,
    setStyle,
    backgroundId,
    setBackgroundId,
    backgroundColor,
    setBackgroundColor,
    backgroundImage,
    setBackgroundImage,
    resetToDefaults,
  } = useTheme();
  const toast = useToast();
  const bgFileRef = useRef(null);

  async function handleBackgroundFile(e) {
    const file = e.target.files?.[0];
    e.target.value = ""; // 允許重選同一個檔案
    if (!file) return;
    try {
      const { dataUrl } = await downscaleImage(file, { maxSize: 1920, quality: 0.82 });
      if (dataUrl.length > BG_IMAGE_MAX_CHARS) {
        toast.error("圖片壓縮後仍太大，請換一張小一點的圖");
        return;
      }
      setBackgroundImage(dataUrl);
      setBackgroundId("custom-image");
      toast.success("背景圖已套用");
    } catch (err) {
      toast.error(err?.message ?? "背景圖讀取失敗");
    }
  }

  function removeBackgroundImage() {
    setBackgroundImage("");
    // 花色守衛會自動退回預設，這裡直接切掉避免一瞬間的空背景
    if (backgroundId === "custom-image") setBackgroundId(THEME_DEFAULTS.backgroundId);
  }

  // 有上傳圖時，背景 gallery 多一個「自訂圖片」選項
  const backgroundOptions = backgroundImage
    ? [
        ...BACKGROUND_OPTIONS,
        {
          id: "custom-image",
          label: "自訂圖片",
          preview: `url("${backgroundImage}") center / cover no-repeat`,
        },
      ]
    : BACKGROUND_OPTIONS;

  // 白底僅限淺色模式、黑底僅限深色模式，不符目前明暗的直接不顯示
  // （theme 為實際套用的明暗，系統模式下是解析後的結果）
  const visibleStyleOptions = STYLE_OPTIONS.filter(
    (opt) =>
      !(opt.key === "white" && theme === "dark") &&
      !(opt.key === "black" && theme === "light")
  );

  // 主色與背景色都未自訂：「跟隨主色」呈現原始三色暈染
  const untouchedAuto =
    !backgroundColor && primaryColor.toLowerCase() === THEME_DEFAULTS.primaryColor;

  function thumbPreview(opt) {
    if (opt.id === "auto-gradient" && untouchedAuto) return CLASSIC_PREVIEW;
    return opt.preview;
  }

  return (
    <div className={styles.card}>
      <h2 className={styles.cardTitle}>外觀</h2>

      <div className={styles.form}>
        <div className={styles.field}>
          <span>主色</span>
          <div className={styles.colorRow}>
            <input
              type="color"
              value={primaryColor}
              onChange={(e) => setPrimaryColor(e.target.value)}
              aria-label="選擇主色"
            />
            <HexInput value={primaryColor} onChange={setPrimaryColor} ariaLabel="主色 HEX 色碼" />
          </div>
          <div className={styles.shadeRow}>
            <span className={styles.shadeLight}>淺</span>
            <span className={styles.shadeBase}>主</span>
            <span className={styles.shadeDark}>深</span>
          </div>
          <p className={styles.rowMeta}>淺色與深色色階會依主色的明度自動推算</p>
        </div>

        <OptionGroup label="風格" options={visibleStyleOptions} value={style} onSelect={setStyle} />

        {/* 背景：與風格無關的同一組花色 */}
        <div className={styles.field}>
          <span>背景</span>

          {/* 漸層背景的基準色可與主色分開設定；
              三種風格的所有花色都由基準色衍生，picker 永遠顯示 */}
          <div className={styles.colorRow}>
            <input
              type="color"
              value={backgroundColor || primaryColor}
              onChange={(e) => setBackgroundColor(e.target.value)}
              aria-label="選擇背景顏色"
            />
            <HexInput
              value={backgroundColor || primaryColor}
              onChange={setBackgroundColor}
              ariaLabel="背景 HEX 色碼"
            />
            {!backgroundColor && (
              <span className={styles.rowMeta}>跟隨主色中，可另選背景色</span>
            )}
          </div>
          
          <div className={styles.bgGallery}>
            {backgroundOptions.map((opt) => (
              <button
                key={opt.id}
                type="button"
                className={backgroundId === opt.id ? styles.bgThumbActive : styles.bgThumb}
                style={{ background: thumbPreview(opt) }}
                onClick={() => setBackgroundId(opt.id)}
              >
                <span className={styles.bgThumbLabel}>
                  {opt.id === "auto-gradient" && backgroundColor ? "自訂顏色" : opt.label}
                </span>
              </button>
            ))}
          </div>

          {/* 上傳自訂背景圖（存在瀏覽器本地，重設或移除即刪掉） */}
          <input
            ref={bgFileRef}
            type="file"
            accept="image/*"
            hidden
            onChange={handleBackgroundFile}
          />
          <div className={styles.formActions}>
            <button
              type="button"
              className={styles.btnSecondary}
              onClick={() => bgFileRef.current?.click()}
            >
              <MIcon name="upload" size={16} />
              上傳背景圖
            </button>
            {backgroundImage && (
              <button type="button" className={styles.btnSecondary} onClick={removeBackgroundImage}>
                <MIcon name="delete" size={16} />
                移除背景圖
              </button>
            )}
          </div>
        </div>

        <OptionGroup label="明暗模式" options={THEME_OPTIONS} value={mode} onSelect={setMode} />

        <div className={styles.formActions}>
          <button type="button" className={styles.btnSecondary} onClick={resetToDefaults}>
            <MIcon name="refresh" size={16} />
            重設為系統預設值
          </button>
        </div>
      </div>
    </div>
  );
}
