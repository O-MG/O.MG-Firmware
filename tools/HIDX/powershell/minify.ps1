function Minify-Script {
    param(
        [Parameter(Mandatory=$true)]
        [string]$InputFilePath,
        [Parameter(Mandatory=$true)]
        [string]$OutputFilePath,
        [switch]$AsBase64
    )

    $content = Get-Content $InputFilePath -Raw

    # Remove multi-line comments
    $content = [regex]::Replace($content, '<#.*?#>', '', [System.Text.RegularExpressions.RegexOptions]::Singleline)

    # Remove single-line comments
    $content = [regex]::Replace($content, '#.*', '')

    # Remove unnecessary whitespaces
    $content = [regex]::Replace($content, '\s+', ' ')

    if ($AsBase64) {
        $contentBytes = [System.Text.Encoding]::UTF8.GetBytes($content)
        $contentBase64 = [System.Convert]::ToBase64String($contentBytes)
        Set-Content -Path $OutputFilePath -Value $contentBase64
    }
    else {
        Set-Content -Path $OutputFilePath -Value $content
    }
}

# Example usage:
Minify-Script -InputFilePath "HIDXExfil.ps1" -OutputFilePath "HIDXExfil-minified.ps1" -AsBase64

