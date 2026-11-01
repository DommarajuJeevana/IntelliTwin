export default function Card({ children, className = "", as: Tag = "div", ...props }) {
  return (
    <Tag className={`card p-5 ${className}`} {...props}>
      {children}
    </Tag>
  );
}
