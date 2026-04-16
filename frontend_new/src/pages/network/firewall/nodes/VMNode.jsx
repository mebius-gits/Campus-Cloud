import { Handle, Position } from "@xyflow/react";
import styles from "../FirewallPage.module.scss";

const STATUS_COLOR = { running: "#38a169", stopped: "#e53e3e" };

const MIcon = ({ name, size = 18 }) => (
  <span className="material-icons-outlined" style={{ fontSize: size, lineHeight: 1 }}>
    {name}
  </span>
);

export default function VMNode({ data, selected }) {
  const statusColor = STATUS_COLOR[data.status] ?? "#a0aec0";
  return (
    <div className={`${styles.vmNode} ${selected ? styles.nodeSelected : ""}`}>
      <Handle type="target" position={Position.Left}  className={styles.handleIn} />
      <div className={styles.vmStatus} style={{ background: statusColor }} />
      <div className={styles.vmInfo}>
        <span className={styles.vmName}>{data.name}</span>
        <span className={styles.vmMeta}>{data.ip_address ?? `vmid:${data.vmid}`}</span>
      </div>
      <MIcon name={data.firewall_enabled ? "security" : "shield"} size={15} />
      <Handle type="source" position={Position.Right} className={styles.handleOut} />
    </div>
  );
}
