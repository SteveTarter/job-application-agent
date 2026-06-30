import { NextRequest, NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get("file") as File | null;
    if (!file) {
      return NextResponse.json({ error: "No file uploaded" }, { status: 400 });
    }

    // Convert to Node Buffer
    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // Create a local uploads directory in the parent workspace directory
    const uploadDir = path.join(process.cwd(), "..", "tmp_uploads");
    await fs.mkdir(uploadDir, { recursive: true });

    // Use a unique name or sanitize original name
    const timestamp = Date.now();
    const sanitizedFilename = `${timestamp}_${file.name.replace(/[^a-zA-Z0-9.-]/g, "_")}`;
    const filePath = path.join(uploadDir, sanitizedFilename);
    
    await fs.writeFile(filePath, buffer);

    // Get the absolute path
    const absolutePath = path.resolve(filePath);
    return NextResponse.json({ path: absolutePath });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
