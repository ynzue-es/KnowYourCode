import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

/**
 * L'icône du raccourci iOS. Un PNG est obligatoire ici : Safari ignore le SVG
 * pour l'écran d'accueil, et servirait une capture de la page à la place.
 *
 * Le dessin reprend les chevrons du logo, épaissis : à 180 pixels, le trait
 * fin de l'icône d'origine disparaîtrait.
 */
export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#1f2023",
          color: "#f5f6f8",
          fontSize: 74,
          fontWeight: 700,
          letterSpacing: -4,
          fontFamily: "monospace",
        }}
      >
        {"</>"}
      </div>
    ),
    { ...size },
  );
}
