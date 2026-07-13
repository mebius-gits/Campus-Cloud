import { useEffect, useState } from "react";
import styles from "./Avatar.module.scss";

/* ── 共用頭像（sidebar 與個人資料綁定同一份樣式） ──
   有 avatar_url 顯示圖片，未設定或載入失敗則退回姓名縮寫。
   src 可覆寫 user.avatar_url（個人資料編輯模式的即時預覽用） */
export default function Avatar({ user, src, size = 32, className }) {
  const url = src !== undefined ? src : user?.avatar_url;
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [url]);

  const initial = (user?.full_name || user?.email || "U").slice(0, 1).toUpperCase();

  return (
    <div
      className={`${styles.avatar}${className ? ` ${className}` : ""}`}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.44) }}
    >
      {url && !failed ? (
        <img src={url} alt="" onError={() => setFailed(true)} />
      ) : (
        initial
      )}
    </div>
  );
}
