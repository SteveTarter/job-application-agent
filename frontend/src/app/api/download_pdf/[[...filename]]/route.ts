import { NextRequest, NextResponse } from "next/server";
import { jsPDF } from "jspdf";

export async function POST(req: NextRequest) {
  try {
    let text = "";
    let candidateName = "";
    let company = "";

    const contentType = req.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const body = await req.json();
      text = body.text;
      candidateName = body.candidateName;
      company = body.company;
    } else {
      const formData = await req.formData();
      text = formData.get("text") as string || "";
      candidateName = formData.get("candidateName") as string || "";
      company = formData.get("company") as string || "";
    }

    const doc = new jsPDF({
      orientation: "portrait",
      unit: "pt",
      format: "letter",
    });

    const margin = 72; // 1 inch margin
    const pageWidth = 612; // 8.5 inches
    const pageHeight = 792; // 11 inches
    const maxWidth = pageWidth - margin * 2;
    const startY = margin;

    // Configure standard serif font
    doc.setFont("times", "normal");
    doc.setFontSize(11);

    const lines = doc.splitTextToSize(text || "", maxWidth);
    let cursorY = startY;
    const lineHeight = 16;

    for (let i = 0; i < lines.length; i++) {
      if (cursorY + lineHeight > pageHeight - margin) {
        doc.addPage();
        cursorY = margin;
      }
      doc.text(lines[i], margin, cursorY);
      cursorY += lineHeight;
    }

    // Output PDF as ArrayBuffer
    const pdfBuffer = doc.output("arraybuffer");

    const cleanName = (candidateName || "Candidate").replace(/\s+/g, "");
    const cleanCompany = (company || "Company").replace(/\s+/g, "");
    const filename = `CoverLetter-${cleanName}-${cleanCompany}.pdf`;

    return new NextResponse(pdfBuffer, {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": `inline; filename="${filename}"`,
        "Cache-Control": "no-cache",
      },
    });
  } catch (error: any) {
    console.error("Failed to generate PDF on server:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
