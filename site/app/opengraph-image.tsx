import { ImageResponse } from "next/og";

export const alt = "KnowYourCode — on délègue le code, pas la compréhension";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/** L'image de partage, dessinée aux couleurs du panneau. */
export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          backgroundColor: "#0b0c0e",
          padding: 80,
        }}
      >
        <div style={{ display: "flex", alignItems: "center" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 96,
              height: 96,
              borderRadius: 24,
              backgroundColor: "#1f2023",
              border: "3px solid #33363b",
              color: "#f5f6f8",
              fontSize: 44,
              fontWeight: 700,
            }}
          >
            {"</>"}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{
              display: "flex",
              color: "#f5f6f8",
              fontSize: 76,
              fontWeight: 700,
              letterSpacing: -2,
            }}
          >
            KnowYourCode
          </div>
          <div
            style={{
              display: "flex",
              marginTop: 20,
              color: "#9298a2",
              fontSize: 34,
              lineHeight: 1.35,
            }}
          >
            On délègue le code. Pas la compréhension.
          </div>
        </div>

        <div
          style={{
            display: "flex",
            color: "#767c86",
            fontSize: 26,
          }}
        >
          Utilitaire de barre de menus pour macOS
        </div>
      </div>
    ),
    { ...size },
  );
}
