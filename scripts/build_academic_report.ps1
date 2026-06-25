param(
    [string]$Source = "report/BAO_CAO_DO_AN.md",
    [string]$OutputDocx = "report/BAO_CAO_DO_AN.docx",
    [string]$OutputPdf = "report/BAO_CAO_DO_AN.pdf",
    [string]$RenderDir = "target/report-render"
)

$ErrorActionPreference = "Stop"

# Document design:
# - Base preset: narrative_proposal.
# - Named override "VietnameseAcademic": A4, Times New Roman, 13 pt,
#   justified body, 1.35 line spacing, restrained blue headings.

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sourcePath = [IO.Path]::GetFullPath((Join-Path $repo $Source))
$docxPath = [IO.Path]::GetFullPath((Join-Path $repo $OutputDocx))
$pdfPath = [IO.Path]::GetFullPath((Join-Path $repo $OutputPdf))
$renderPath = [IO.Path]::GetFullPath((Join-Path $repo $RenderDir))
$assetPath = Join-Path $repo "report\assets"

New-Item -ItemType Directory -Force -Path (Split-Path $docxPath), $renderPath, $assetPath | Out-Null

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function New-Canvas {
    param([int]$Width = 1600, [int]$Height = 900)
    $bitmap = New-Object Drawing.Bitmap($Width, $Height)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.TextRenderingHint = [Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $graphics.Clear([Drawing.Color]::White)
    return @($bitmap, $graphics)
}

function Save-Canvas {
    param($Bitmap, $Graphics, [string]$Path)
    $Graphics.Dispose()
    $Bitmap.Save($Path, [Drawing.Imaging.ImageFormat]::Png)
    $Bitmap.Dispose()
}

function Draw-Title {
    param($Graphics, [string]$Text, [int]$Width)
    $font = New-Object Drawing.Font("Arial", 26, [Drawing.FontStyle]::Bold)
    $brush = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(31, 78, 121))
    $format = New-Object Drawing.StringFormat
    $format.Alignment = [Drawing.StringAlignment]::Center
    $Graphics.DrawString($Text, $font, $brush, (New-Object Drawing.RectangleF(40, 28, ($Width - 80), 60)), $format)
    $font.Dispose()
    $brush.Dispose()
    $format.Dispose()
}

function New-RatingChart {
    param([string]$Path)
    $canvas = New-Canvas
    $bmp = $canvas[0]
    $g = $canvas[1]
    Draw-Title $g "MovieLens 1M rating distribution" 1600
    $labels = @("1", "2", "3", "4", "5")
    $values = @(56174, 107557, 261197, 348971, 226310)
    $max = 380000.0
    $left = 145
    $bottom = 770
    $chartHeight = 610
    $barWidth = 175
    $gap = 85
    $axisPen = New-Object Drawing.Pen([Drawing.Color]::FromArgb(80, 80, 80), 2)
    $gridPen = New-Object Drawing.Pen([Drawing.Color]::FromArgb(225, 229, 234), 1)
    $barBrush = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(46, 116, 181))
    $font = New-Object Drawing.Font("Arial", 18)
    $small = New-Object Drawing.Font("Arial", 15)
    $textBrush = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(40, 40, 40))
    for ($i = 0; $i -le 4; $i++) {
        $y = $bottom - ($i * $chartHeight / 4)
        $g.DrawLine($gridPen, $left, $y, 1510, $y)
        $tick = [int]($max * $i / 4)
        $g.DrawString(("{0:N0}" -f $tick), $small, $textBrush, 20, ($y - 12))
    }
    $g.DrawLine($axisPen, $left, 140, $left, $bottom)
    $g.DrawLine($axisPen, $left, $bottom, 1510, $bottom)
    for ($i = 0; $i -lt $values.Count; $i++) {
        $x = $left + 115 + $i * ($barWidth + $gap)
        $h = $values[$i] / $max * $chartHeight
        $g.FillRectangle($barBrush, $x, ($bottom - $h), $barWidth, $h)
        $g.DrawString($labels[$i], $font, $textBrush, ($x + 77), 792)
        $g.DrawString(("{0:N0}" -f $values[$i]), $small, $textBrush, ($x + 24), ($bottom - $h - 34))
    }
    $g.DrawString("Rating", $font, $textBrush, 790, 835)
    $axisPen.Dispose(); $gridPen.Dispose(); $barBrush.Dispose()
    $font.Dispose(); $small.Dispose(); $textBrush.Dispose()
    Save-Canvas $bmp $g $Path
}

function New-QualityChart {
    param([string]$Path)
    $canvas = New-Canvas
    $bmp = $canvas[0]
    $g = $canvas[1]
    Draw-Title $g "Quality comparison on MovieLens 1M" 1600
    $metrics = @("Prediction coverage", "Hit Rate@10", "NDCG@10", "MRR@10")
    $cosine = @(20.5132, 0.2562, 0.1210, 0.0814)
    $co = @(37.2020, 2.7327, 1.2108, 0.7559)
    $max = 40.0
    $left = 290
    $top = 160
    $rowHeight = 145
    $usable = 1120
    $blue = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(46, 116, 181))
    $gold = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(211, 145, 45))
    $text = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(40, 40, 40))
    $grid = New-Object Drawing.Pen([Drawing.Color]::FromArgb(225, 229, 234), 1)
    $font = New-Object Drawing.Font("Arial", 17)
    $small = New-Object Drawing.Font("Arial", 14)
    for ($i = 0; $i -lt $metrics.Count; $i++) {
        $y = $top + $i * $rowHeight
        $g.DrawString($metrics[$i], $font, $text, 28, ($y + 25))
        $g.DrawLine($grid, $left, ($y + 110), ($left + $usable), ($y + 110))
        $w1 = $cosine[$i] / $max * $usable
        $w2 = $co[$i] / $max * $usable
        $g.FillRectangle($blue, $left, $y, $w1, 38)
        $g.FillRectangle($gold, $left, ($y + 50), $w2, 38)
        $g.DrawString(("{0:N3}%" -f $cosine[$i]), $small, $text, ($left + $w1 + 10), ($y + 8))
        $g.DrawString(("{0:N3}%" -f $co[$i]), $small, $text, ($left + $w2 + 10), ($y + 58))
    }
    $g.FillRectangle($blue, 530, 760, 40, 20)
    $g.DrawString("Cosine", $font, $text, 580, 755)
    $g.FillRectangle($gold, 790, 760, 40, 20)
    $g.DrawString("Co-occurrence", $font, $text, 840, 755)
    $blue.Dispose(); $gold.Dispose(); $text.Dispose(); $grid.Dispose()
    $font.Dispose(); $small.Dispose()
    Save-Canvas $bmp $g $Path
}

function New-RuntimeChart {
    param([string]$Path)
    $canvas = New-Canvas
    $bmp = $canvas[0]
    $g = $canvas[1]
    Draw-Title $g "Pipeline stage runtime" 1600
    $labels = @("User history", "Pair statistics", "Similarity", "Scoring", "Top-K", "Evaluation")
    $cosine = @(7.482733, 403.542386, 53.930883, 341.456832, 34.709436, 19.833109)
    $co = @(7.482733, 403.542386, 58.726546, 255.126903, 11.857925, 7.069902)
    $max = 430.0
    $left = 300
    $top = 125
    $rowHeight = 105
    $usable = 1120
    $blue = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(46, 116, 181))
    $gold = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(211, 145, 45))
    $text = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(40, 40, 40))
    $font = New-Object Drawing.Font("Arial", 16)
    $small = New-Object Drawing.Font("Arial", 13)
    for ($i = 0; $i -lt $labels.Count; $i++) {
        $y = $top + $i * $rowHeight
        $g.DrawString($labels[$i], $font, $text, 28, ($y + 19))
        $w1 = $cosine[$i] / $max * $usable
        $w2 = $co[$i] / $max * $usable
        $g.FillRectangle($blue, $left, $y, $w1, 31)
        $g.FillRectangle($gold, $left, ($y + 42), $w2, 31)
        $g.DrawString(("{0:N2} s" -f $cosine[$i]), $small, $text, ($left + $w1 + 8), ($y + 5))
        $g.DrawString(("{0:N2} s" -f $co[$i]), $small, $text, ($left + $w2 + 8), ($y + 47))
    }
    $g.FillRectangle($blue, 530, 790, 40, 20)
    $g.DrawString("Cosine", $font, $text, 580, 785)
    $g.FillRectangle($gold, 790, 790, 40, 20)
    $g.DrawString("Co-occurrence", $font, $text, 840, 785)
    $blue.Dispose(); $gold.Dispose(); $text.Dispose()
    $font.Dispose(); $small.Dispose()
    Save-Canvas $bmp $g $Path
}

function New-ScalabilityChart {
    param([string]$Path)
    $canvas = New-Canvas
    $bmp = $canvas[0]
    $g = $canvas[1]
    Draw-Title $g "Synthetic smoke benchmark (Docker local mode)" 1600
    $labels = @("250", "1,000", "3,000")
    $cosine = @(12.498293, 12.386769, 14.355665)
    $co = @(12.547529, 13.366060, 15.885973)
    $max = 18.0
    $left = 190
    $bottom = 760
    $chartHeight = 580
    $barWidth = 135
    $groupWidth = 390
    $blue = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(46, 116, 181))
    $gold = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(211, 145, 45))
    $text = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(40, 40, 40))
    $grid = New-Object Drawing.Pen([Drawing.Color]::FromArgb(225, 229, 234), 1)
    $axis = New-Object Drawing.Pen([Drawing.Color]::FromArgb(80, 80, 80), 2)
    $font = New-Object Drawing.Font("Arial", 17)
    $small = New-Object Drawing.Font("Arial", 14)
    for ($i = 0; $i -le 3; $i++) {
        $y = $bottom - ($i * $chartHeight / 3)
        $g.DrawLine($grid, $left, $y, 1460, $y)
        $g.DrawString(("{0:N0}" -f ($max * $i / 3)), $small, $text, 110, ($y - 10))
    }
    $g.DrawLine($axis, $left, 160, $left, $bottom)
    $g.DrawLine($axis, $left, $bottom, 1460, $bottom)
    for ($i = 0; $i -lt $labels.Count; $i++) {
        $x = $left + 135 + $i * $groupWidth
        $h1 = $cosine[$i] / $max * $chartHeight
        $h2 = $co[$i] / $max * $chartHeight
        $g.FillRectangle($blue, $x, ($bottom - $h1), $barWidth, $h1)
        $g.FillRectangle($gold, ($x + $barWidth + 20), ($bottom - $h2), $barWidth, $h2)
        $g.DrawString(("{0:N2}" -f $cosine[$i]), $small, $text, ($x + 25), ($bottom - $h1 - 31))
        $g.DrawString(("{0:N2}" -f $co[$i]), $small, $text, ($x + $barWidth + 44), ($bottom - $h2 - 31))
        $g.DrawString($labels[$i], $font, $text, ($x + 93), 790)
    }
    $g.DrawString("Ratings", $font, $text, 760, 835)
    $g.FillRectangle($blue, 530, 105, 40, 20)
    $g.DrawString("Cosine", $font, $text, 580, 100)
    $g.FillRectangle($gold, 790, 105, 40, 20)
    $g.DrawString("Co-occurrence", $font, $text, 840, 100)
    $blue.Dispose(); $gold.Dispose(); $text.Dispose(); $grid.Dispose(); $axis.Dispose()
    $font.Dispose(); $small.Dispose()
    Save-Canvas $bmp $g $Path
}

function New-ArchitectureDiagram {
    param([string]$Path)
    $canvas = New-Canvas 1800 1050
    $bmp = $canvas[0]
    $g = $canvas[1]
    Draw-Title $g "Offline recommendation pipeline" 1800
    $boxBrush = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(232, 238, 245))
    $accentBrush = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(46, 116, 181))
    $testBrush = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(255, 244, 214))
    $border = New-Object Drawing.Pen([Drawing.Color]::FromArgb(46, 116, 181), 3)
    $arrow = New-Object Drawing.Pen([Drawing.Color]::FromArgb(90, 90, 90), 4)
    $arrow.CustomEndCap = New-Object Drawing.Drawing2D.AdjustableArrowCap(7, 7)
    $font = New-Object Drawing.Font("Arial", 16, [Drawing.FontStyle]::Bold)
    $small = New-Object Drawing.Font("Arial", 14)
    $text = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(35, 35, 35))
    $white = New-Object Drawing.SolidBrush([Drawing.Color]::White)
    $format = New-Object Drawing.StringFormat
    $format.Alignment = [Drawing.StringAlignment]::Center
    $format.LineAlignment = [Drawing.StringAlignment]::Center
    $boxes = @(
        @{X=80;Y=160;W=250;H=100;T="MovieLens 1M"},
        @{X=390;Y=160;W=250;H=100;T="Preprocess UTC"},
        @{X=700;Y=160;W=250;H=100;T="Temporal split"},
        @{X=1010;Y=160;W=250;H=100;T="User history"},
        @{X=1320;Y=160;W=340;H=100;T="Pair statistics"}
    )
    foreach ($b in $boxes) {
        $rect = New-Object Drawing.RectangleF($b.X,$b.Y,$b.W,$b.H)
        $g.FillRectangle($boxBrush,$rect); $g.DrawRectangle($border,$b.X,$b.Y,$b.W,$b.H)
        $g.DrawString($b.T,$font,$text,$rect,$format)
    }
    for ($i=0;$i -lt 4;$i++) {
        $a=$boxes[$i];$b=$boxes[$i+1]
        $g.DrawLine($arrow,($a.X+$a.W),($a.Y+$a.H/2),$b.X,($b.Y+$b.H/2))
    }
    $methodBoxes = @(
        @{X=260;Y=430;W=300;H=105;T="Cosine Top-L"},
        @{X=660;Y=430;W=300;H=105;T="Co-occurrence Top-L"},
        @{X=260;Y=650;W=300;H=105;T="Scoring + Top-K"},
        @{X=660;Y=650;W=300;H=105;T="Scoring + Top-K"}
    )
    foreach ($b in $methodBoxes) {
        $rect = New-Object Drawing.RectangleF($b.X,$b.Y,$b.W,$b.H)
        $g.FillRectangle($boxBrush,$rect); $g.DrawRectangle($border,$b.X,$b.Y,$b.W,$b.H)
        $g.DrawString($b.T,$font,$text,$rect,$format)
    }
    $g.DrawLine($arrow,1490,260,410,430)
    $g.DrawLine($arrow,1490,260,810,430)
    $g.DrawLine($arrow,410,535,410,650)
    $g.DrawLine($arrow,810,535,810,650)
    $evalRect = New-Object Drawing.RectangleF(1090,650,300,105)
    $g.FillRectangle($accentBrush,$evalRect); $g.DrawRectangle($border,1090,650,300,105)
    $g.DrawString("Offline evaluation",$font,$white,$evalRect,$format)
    $g.DrawLine($arrow,560,702,1090,702)
    $g.DrawLine($arrow,960,702,1090,702)
    $testRect = New-Object Drawing.RectangleF(1090,430,300,105)
    $g.FillRectangle($testBrush,$testRect); $g.DrawRectangle($border,1090,430,300,105)
    $g.DrawString("Held-out test only",$font,$text,$testRect,$format)
    $g.DrawLine($arrow,825,260,1240,430)
    $g.DrawLine($arrow,1240,535,1240,650)
    $demoRect = New-Object Drawing.RectangleF(1460,650,260,105)
    $g.FillRectangle($accentBrush,$demoRect); $g.DrawRectangle($border,1460,650,260,105)
    $g.DrawString("Streamlit read-only",$font,$white,$demoRect,$format)
    $g.DrawLine($arrow,1390,702,1460,702)
    $g.DrawString("The held-out test bypasses every model-building stage.",$small,$text,520,900)
    $boxBrush.Dispose(); $accentBrush.Dispose(); $testBrush.Dispose()
    $border.Dispose(); $arrow.Dispose(); $font.Dispose(); $small.Dispose()
    $text.Dispose(); $white.Dispose(); $format.Dispose()
    Save-Canvas $bmp $g $Path
}

New-RatingChart (Join-Path $assetPath "rating_distribution.png")
New-QualityChart (Join-Path $assetPath "method_quality.png")
New-RuntimeChart (Join-Path $assetPath "stage_runtime.png")
New-ScalabilityChart (Join-Path $assetPath "scalability_runtime.png")
New-ArchitectureDiagram (Join-Path $assetPath "pipeline_architecture.png")

$lines = Get-Content -LiteralPath $sourcePath -Encoding UTF8

function Clean-InlineMarkdown {
    param([string]$Text)
    $value = $Text
    $value = $value -replace '\*\*([^*]+)\*\*', '$1'
    $value = $value -replace '`([^`]+)`', '$1'
    $value = $value -replace '\*([^*]+)\*', '$1'
    return $value
}

$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Add()

    $section = $doc.Sections.Item(1)
    $section.PageSetup.PaperSize = 7 # wdPaperA4
    $section.PageSetup.TopMargin = $word.CentimetersToPoints(2.5)
    $section.PageSetup.BottomMargin = $word.CentimetersToPoints(2.5)
    $section.PageSetup.LeftMargin = $word.CentimetersToPoints(2.8)
    $section.PageSetup.RightMargin = $word.CentimetersToPoints(2.2)
    $section.PageSetup.HeaderDistance = $word.CentimetersToPoints(1.25)
    $section.PageSetup.FooterDistance = $word.CentimetersToPoints(1.25)

    $normal = $doc.Styles.Item("Normal")
    $normal.Font.Name = "Times New Roman"
    $normal.Font.Size = 13
    $normal.ParagraphFormat.Alignment = 3
    $normal.ParagraphFormat.SpaceAfter = 6
    $normal.ParagraphFormat.LineSpacingRule = 5
    $normal.ParagraphFormat.LineSpacing = 17.5
    $normal.ParagraphFormat.FirstLineIndent = $word.CentimetersToPoints(1)

    $heading1 = $doc.Styles.Item("Heading 1")
    $heading1.Font.Name = "Times New Roman"
    $heading1.Font.Size = 16
    $heading1.Font.Bold = $true
    $heading1.Font.Color = 5186607
    $heading1.ParagraphFormat.SpaceBefore = 18
    $heading1.ParagraphFormat.SpaceAfter = 10
    $heading1.ParagraphFormat.KeepWithNext = $true
    $heading1.ParagraphFormat.FirstLineIndent = 0
    $heading1.ParagraphFormat.OutlineLevel = 1

    $heading2 = $doc.Styles.Item("Heading 2")
    $heading2.Font.Name = "Times New Roman"
    $heading2.Font.Size = 14
    $heading2.Font.Bold = $true
    $heading2.Font.Color = 5186607
    $heading2.ParagraphFormat.SpaceBefore = 12
    $heading2.ParagraphFormat.SpaceAfter = 6
    $heading2.ParagraphFormat.KeepWithNext = $true
    $heading2.ParagraphFormat.FirstLineIndent = 0
    $heading2.ParagraphFormat.OutlineLevel = 2

    $heading3 = $doc.Styles.Item("Heading 3")
    $heading3.Font.Name = "Times New Roman"
    $heading3.Font.Size = 13
    $heading3.Font.Bold = $true
    $heading3.Font.Color = 5133399
    $heading3.ParagraphFormat.SpaceBefore = 8
    $heading3.ParagraphFormat.SpaceAfter = 4
    $heading3.ParagraphFormat.KeepWithNext = $true
    $heading3.ParagraphFormat.FirstLineIndent = 0
    $heading3.ParagraphFormat.OutlineLevel = 3

    function Add-DocParagraph {
        param(
            [string]$Text,
            [string]$Style = "Normal",
            [int]$Alignment = -1,
            [double]$Size = 0,
            [bool]$Bold = $false,
            [bool]$Italic = $false,
            [string]$Font = ""
        )
        $range = $doc.Range($doc.Content.End - 1, $doc.Content.End - 1)
        $paragraph = $doc.Paragraphs.Add($range)
        $paragraph.Range.Text = (Clean-InlineMarkdown $Text)
        try { $paragraph.Range.Style = $doc.Styles.Item($Style) } catch {}
        try { $paragraph.Range.ListFormat.RemoveNumbers() } catch {}
        if ($Alignment -ge 0) { $paragraph.Alignment = $Alignment }
        if ($Size -gt 0) { $paragraph.Range.Font.Size = $Size }
        if ($Bold) { $paragraph.Range.Font.Bold = $true }
        if ($Italic) { $paragraph.Range.Font.Italic = $true }
        if ($Font) { $paragraph.Range.Font.Name = $Font }
        $paragraph.Range.InsertParagraphAfter()
        return $paragraph
    }

    function Add-PageBreak {
        $range = $doc.Range($doc.Content.End - 1, $doc.Content.End - 1)
        $range.InsertBreak(7)
    }

    function Add-TableFromRows {
        param([object[]]$Rows)
        if ($Rows.Count -lt 2) { return }
        $dataRows = @()
        foreach ($row in $Rows) {
            if ($row -match '^\s*\|?[\s:\-\|]+\|?\s*$') { continue }
            $cells = $row.Trim().Trim("|").Split("|") | ForEach-Object { (Clean-InlineMarkdown $_.Trim()) }
            $dataRows += ,@($cells)
        }
        if ($dataRows.Count -eq 0) { return }
        $cols = $dataRows[0].Count
        $range = $doc.Range($doc.Content.End - 1, $doc.Content.End - 1)
        $table = $doc.Tables.Add($range, $dataRows.Count, $cols)
        $table.AllowAutoFit = $false
        $table.Borders.Enable = 1
        $table.Rows.Item(1).HeadingFormat = -1
        try { $table.Range.ListFormat.RemoveNumbers() } catch {}
        $table.Range.Font.Name = "Times New Roman"
        $table.Range.Font.Size = 10.5
        $table.Range.ParagraphFormat.SpaceAfter = 0
        $table.Range.ParagraphFormat.FirstLineIndent = 0
        $table.Range.ParagraphFormat.LineSpacingRule = 0
        [double]$totalWidth = 439.37
        if ($cols -eq 2) {
            $widths = @(($totalWidth * 0.34), ($totalWidth * 0.66))
        } elseif ($cols -eq 3) {
            $widths = @(($totalWidth * 0.46), ($totalWidth * 0.27), ($totalWidth * 0.27))
        } elseif ($cols -eq 4) {
            $widths = @(($totalWidth * 0.34), ($totalWidth * 0.22), ($totalWidth * 0.22), ($totalWidth * 0.22))
        } else {
            $widths = 1..$cols | ForEach-Object { $totalWidth / $cols }
        }
        for ($c = 1; $c -le $cols; $c++) {
            $table.Columns.Item($c).Width = $widths[$c - 1]
        }
        for ($r = 0; $r -lt $dataRows.Count; $r++) {
            for ($c = 0; $c -lt $cols; $c++) {
                $cell = $table.Cell($r + 1, $c + 1)
                $cell.Range.Text = [string]$dataRows[$r][$c]
                $cell.VerticalAlignment = 1
                if ($r -eq 0) {
                    $cell.Range.Font.Bold = $true
                    $cell.Shading.BackgroundPatternColor = 15132390
                    $cell.Range.ParagraphFormat.Alignment = 1
                } elseif ($c -gt 0 -and $cell.Range.Text -match '[0-9]') {
                    $cell.Range.ParagraphFormat.Alignment = 1
                } else {
                    $cell.Range.ParagraphFormat.Alignment = 0
                }
            }
        }
        $table.Range.InsertParagraphAfter()
        $after = $doc.Paragraphs.Item($doc.Paragraphs.Count)
        $after.Format.SpaceAfter = 6
    }

    function Add-Image {
        param([string]$RelativePath, [string]$Caption)
        $full = [IO.Path]::GetFullPath((Join-Path (Split-Path $sourcePath) $RelativePath))
        $range = $doc.Range($doc.Content.End - 1, $doc.Content.End - 1)
        $p = $doc.Paragraphs.Add($range)
        $p.Alignment = 1
        $p.Format.SpaceBefore = 8
        $p.Format.SpaceAfter = 3
        $shape = $p.Range.InlineShapes.AddPicture($full)
        if ($shape.Width -gt $word.CentimetersToPoints(15.2)) {
            $ratio = $word.CentimetersToPoints(15.2) / $shape.Width
            $shape.Width = $shape.Width * $ratio
            $shape.Height = $shape.Height * $ratio
        }
        $p.Range.InsertParagraphAfter()
        $captionParagraph = Add-DocParagraph -Text $Caption -Style "Normal" -Alignment 1 -Size 11 -Italic $true
        $captionParagraph.Format.FirstLineIndent = 0
        $captionParagraph.Format.SpaceAfter = 9
    }

    # Cover page from the source block.
    $coverLines = @()
    $coverEnd = [Array]::IndexOf($lines, "[COVER-END]")
    if ($coverEnd -lt 0) { throw "Missing [COVER-END] marker." }
    for ($i = 0; $i -lt $coverEnd; $i++) {
        if ($lines[$i].Trim()) { $coverLines += $lines[$i].Trim() }
    }
    Add-DocParagraph "" "Normal" 1 13 | Out-Null
    Add-DocParagraph "" "Normal" 1 13 | Out-Null
    Add-DocParagraph "BÁO CÁO ĐỒ ÁN MÔN HỌC" "Normal" 1 18 $true | Out-Null
    Add-DocParagraph "" "Normal" 1 13 | Out-Null
    Add-DocParagraph "XÂY DỰNG HỆ THỐNG GỢI Ý PHIM CÓ KHẢ NĂNG MỞ RỘNG BẰNG ITEM-BASED COLLABORATIVE FILTERING VÀ HADOOP MAPREDUCE" "Normal" 1 21 $true | Out-Null
    Add-DocParagraph "" "Normal" 1 13 | Out-Null
    Add-DocParagraph "Báo cáo kỹ thuật và thực nghiệm" "Normal" 1 14 $false $true | Out-Null
    Add-DocParagraph "" "Normal" 1 13 | Out-Null
    Add-DocParagraph "" "Normal" 1 13 | Out-Null
    Add-DocParagraph "Bộ dữ liệu thực nghiệm chính: MovieLens 1M" "Normal" 1 13 $true | Out-Null
    Add-DocParagraph "Java 17 - Apache Hadoop MapReduce 3.5.0 - Maven - Python - Docker - Streamlit" "Normal" 1 12 | Out-Null
    Add-DocParagraph "" "Normal" 1 13 | Out-Null
    Add-DocParagraph "" "Normal" 1 13 | Out-Null
    Add-DocParagraph "Tháng 6 năm 2026" "Normal" 1 13 $true | Out-Null

    $endRange = $doc.Range($doc.Content.End - 1, $doc.Content.End - 1)
    $endRange.InsertBreak(2)
    $mainSection = $doc.Sections.Item(2)
    $mainSection.PageSetup.PaperSize = 7
    $mainSection.PageSetup.TopMargin = $word.CentimetersToPoints(2.5)
    $mainSection.PageSetup.BottomMargin = $word.CentimetersToPoints(2.5)
    $mainSection.PageSetup.LeftMargin = $word.CentimetersToPoints(2.8)
    $mainSection.PageSetup.RightMargin = $word.CentimetersToPoints(2.2)
    $mainSection.PageSetup.HeaderDistance = $word.CentimetersToPoints(1.25)
    $mainSection.PageSetup.FooterDistance = $word.CentimetersToPoints(1.25)
    $mainSection.Headers.Item(1).LinkToPrevious = $false
    $mainSection.Footers.Item(1).LinkToPrevious = $false
    $header = $mainSection.Headers.Item(1).Range
    $header.Text = "HỆ THỐNG GỢI Ý PHIM BẰNG HADOOP MAPREDUCE"
    $header.Font.Name = "Times New Roman"
    $header.Font.Size = 9
    $header.Font.Color = 8421504
    $header.ParagraphFormat.Alignment = 0
    $footer = $mainSection.Footers.Item(1).Range
    $footer.ParagraphFormat.Alignment = 1
    $footer.Font.Name = "Times New Roman"
    $footer.Font.Size = 10
    $footer.Fields.Add($footer, -1, "PAGE", $true) | Out-Null
    $mainSection.Footers.Item(1).PageNumbers.RestartNumberingAtSection = $true
    $mainSection.Footers.Item(1).PageNumbers.StartingNumber = 1

    $i = $coverEnd + 1
    $inCode = $false
    $codeLines = New-Object Collections.Generic.List[string]
    while ($i -lt $lines.Count) {
        $line = $lines[$i]
        $trim = $line.Trim()

        if ($trim -match '^```') {
            if (-not $inCode) {
                $inCode = $true
                $codeLines.Clear()
            } else {
                $inCode = $false
                $p = Add-DocParagraph -Text ($codeLines -join "`r`n") -Style "Normal" -Alignment 0 -Size 9.5 -Font "Consolas"
                $p.Format.FirstLineIndent = 0
                $p.Format.LeftIndent = $word.CentimetersToPoints(0.6)
                $p.Format.RightIndent = $word.CentimetersToPoints(0.3)
                $p.Format.SpaceBefore = 5
                $p.Format.SpaceAfter = 8
                $p.Range.Shading.BackgroundPatternColor = 16119285
            }
            $i++
            continue
        }
        if ($inCode) {
            $codeLines.Add($line)
            $i++
            continue
        }

        if (-not $trim) {
            $i++
            continue
        }

        if ($trim -eq "[TOC]") {
            Add-PageBreak
            Add-DocParagraph "MỤC LỤC" "Normal" 0 16 $true | Out-Null
            Add-DocParagraph "__TOC_PLACEHOLDER__" "Normal" 0 | Out-Null
            Add-PageBreak
            $i++
            continue
        }

        if ($trim -match '^!\[(.+)\]\((.+)\)$') {
            Add-Image $Matches[2] $Matches[1]
            $i++
            continue
        }

        if ($trim.StartsWith("|")) {
            $tableLines = New-Object Collections.Generic.List[string]
            while ($i -lt $lines.Count -and $lines[$i].Trim().StartsWith("|")) {
                $tableLines.Add($lines[$i])
                $i++
            }
            Add-TableFromRows $tableLines.ToArray()
            continue
        }

        if ($trim -match '^# (.+)$') {
            $title = $Matches[1]
            if ($title -match '^(\d+\.|TÀI LIỆU|PHỤ LỤC)') { Add-PageBreak }
            Add-DocParagraph $title "Heading 1" 0 | Out-Null
            $i++
            continue
        }
        if ($trim -match '^## (.+)$') {
            $heading2Text = $Matches[1]
            if ($heading2Text -match '^5\.8\.') {
                Add-PageBreak
            }
            Add-DocParagraph $heading2Text "Heading 2" 0 | Out-Null
            $i++
            continue
        }
        if ($trim -match '^### (.+)$') {
            Add-DocParagraph $Matches[1] "Heading 3" 0 | Out-Null
            $i++
            continue
        }

        if ($trim -match '^(\d+)\.\s+(.+)$') {
            $numberedText = $Matches[1] + ". " + $Matches[2]
            $p = Add-DocParagraph $numberedText "Normal" 0
            $p.Format.FirstLineIndent = -12.76
            $p.Format.LeftIndent = 25.51
            $i++
            continue
        }
        if ($trim -match '^-\s+(.+)$') {
            $p = Add-DocParagraph $Matches[1] "Normal" 0
            $p.Range.ListFormat.ApplyBulletDefault()
            $p.Format.FirstLineIndent = 0
            $p.Format.LeftIndent = $word.CentimetersToPoints(0.9)
            $i++
            continue
        }

        $paragraphLines = New-Object Collections.Generic.List[string]
        while ($i -lt $lines.Count) {
            $candidate = $lines[$i].Trim()
            if (-not $candidate) { break }
            if ($candidate -match '^(#|```|\||!\[|\[TOC\]|\[COVER-END\]|-\s+|\d+\.\s+)') { break }
            $paragraphLines.Add($candidate)
            $i++
        }
        if ($paragraphLines.Count -gt 0) {
            $text = $paragraphLines -join " "
            $p = Add-DocParagraph $text "Normal" 3
            if ($text -match '^(score|sim_|Coverage|MAE|RMSE|Precision|Recall|HitRate|NDCG|MRR|n\(n)') {
                $p.Range.Font.Italic = $true
                $p.Format.Alignment = 1
                $p.Format.FirstLineIndent = 0
            }
        } else {
            $i++
        }
    }

    $tocRange = $doc.Content
    if ($tocRange.Find.Execute("__TOC_PLACEHOLDER__")) {
        $tocRange.Text = ""
        $doc.TablesOfContents.Add($tocRange, $true, 1, 3) | Out-Null
    }
    $doc.Repaginate()
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
    foreach ($field in $doc.Fields) { $field.Update() | Out-Null }

    try {
        $doc.BuiltInDocumentProperties.Item("Title").Value = "Báo cáo đồ án hệ thống gợi ý phim bằng Hadoop MapReduce"
        $doc.BuiltInDocumentProperties.Item("Subject").Value = "Item-Based Collaborative Filtering trên MovieLens 1M"
        $doc.BuiltInDocumentProperties.Item("Author").Value = ""
        $doc.BuiltInDocumentProperties.Item("Company").Value = ""
        $doc.RemoveDocumentInformation(99)
    } catch {}

    $doc.SaveAs2($docxPath, 16)
    $doc.ExportAsFixedFormat($pdfPath, 17)
    $doc.Close($false)
    $doc = $null
    $word.Quit()
    $word = $null
}
finally {
    if ($doc -ne $null) {
        try { $doc.Close($false) } catch {}
    }
    if ($word -ne $null) {
        try { $word.Quit() } catch {}
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

Get-ChildItem -LiteralPath $renderPath -File -ErrorAction SilentlyContinue | Remove-Item -Force
$pdftoppm = (Get-Command pdftoppm -ErrorAction Stop).Source
& $pdftoppm -png -r 130 $pdfPath (Join-Path $renderPath "page")
if ($LASTEXITCODE -ne 0) { throw "pdftoppm render failed with exit code $LASTEXITCODE" }

Write-Output "DOCX: $docxPath"
Write-Output "PDF:  $pdfPath"
Write-Output "QA:   $renderPath"
