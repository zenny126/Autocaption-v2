-- ============================================================
-- AutoCaption - Generate Captions (Local Whisper C++ Engine)
-- Run this script in DaVinci Resolve via: Workspace > Scripts
--
-- Requirements:
--  1. whisper-cli.exe located in the WhisperSubtitler bin directory
-- ============================================================

resolve = Resolve()
local isWindows = FuPLATFORM_WINDOWS

-- ============================================================
-- Helpers
-- ============================================================
local function fileExists(p)
    if not p then return false end
    local f = io.open(p, "r")
    if f then f:close(); return true end
    return false
end

local function runPs1(script)
    if not isWindows then return "" end
    local tmpPs1 = os.getenv("TEMP") .. "\\autocaption_tmp.ps1"
    local tmpOut = os.getenv("TEMP") .. "\\autocaption_tmp_result.txt"
    local f = io.open(tmpPs1, "w")
    if f then
        f:write(script:gsub("__OUT__", tmpOut))
        f:close()
    end
    os.execute('powershell -NoProfile -ExecutionPolicy Bypass -File "' .. tmpPs1 .. '"')
    local result = ""
    local rf = io.open(tmpOut, "r")
    if rf then result = rf:read("*a") or ""; rf:close(); os.remove(tmpOut) end
    os.remove(tmpPs1)
    return result:gsub("^%s*(.-)%s*$", "%1") -- trim whitespace
end

local function showMessage(title, message, askYesNo)
    if isWindows then
        local buttons = askYesNo and "YesNo" or "OK"
        local icon = askYesNo and "Question" or "Information"
        local result = runPs1(
            "Add-Type -AssemblyName System.Windows.Forms\n" ..
            "$r = [System.Windows.Forms.MessageBox]::Show(@'\n" .. message .. "\n'@, @'\n" .. title .. "\n'@, " ..
            "[System.Windows.Forms.MessageBoxButtons]::" .. buttons .. ", " ..
            "[System.Windows.Forms.MessageBoxIcon]::" .. icon .. ")\n" ..
            "Set-Content -Path '__OUT__' -Value $r\n"
        )
        return result == "Yes"
    else
        local safeMsg = message:gsub('"', '\\"'):gsub("\n", " ")
        local safeTitle = title:gsub('"', '\\"')
        local buttons = askYesNo and '{"No", "Yes"}' or '{"OK"}'
        local f = io.popen(string.format(
            'osascript -e \'display dialog "%s" with title "%s" buttons %s default button "%s"\'',
            safeMsg, safeTitle, buttons, askYesNo and "Yes" or "OK"
        ))
        local result = f and f:read("*a") or ""
        if f then f:close() end
        return result:find("Yes") ~= nil
    end
end

local function pickFile(filter, title, initialDir)
    filter = filter or "Media Files|*.mp4;*.mov;*.mkv;*.wav;*.mp3;*.m4a;*.avi|All Files|*.*"
    title = title or "Select audio/video file"
    if isWindows then
        local script = 
            'Add-Type -AssemblyName System.Windows.Forms\n' ..
            '$dlg = New-Object System.Windows.Forms.OpenFileDialog\n' ..
            '$dlg.Filter = "' .. filter .. '"\n' ..
            "$dlg.Title = '" .. title .. "'\n"
        if initialDir and initialDir ~= "" then
            script = script .. '$dlg.InitialDirectory = "' .. initialDir .. '"\n'
        end
        script = script .. 
            "if ($dlg.ShowDialog() -eq 'OK') { Set-Content -Path '__OUT__' -Value $dlg.FileName }" ..
            " else { Set-Content -Path '__OUT__' -Value '' }\n"
        local result = runPs1(script)
        return result ~= "" and result or nil
    else
        local f = io.popen('osascript -e \'POSIX path of (choose file with prompt "' .. title .. '")\'')
        local result = f and f:read("*l") or ""
        if f then f:close() end
        return result ~= "" and result or nil
    end
end

local function getCachedPath(cacheFile)
    local f = io.open(cacheFile, "r")
    if f then
        local path = f:read("*l") or ""
        f:close()
        if path ~= "" and fileExists(path) then
            return path
        end
    end
    return nil
end

local function setCachedPath(cacheFile, path)
    local cf = io.open(cacheFile, "w")
    if cf then
        cf:write(path)
        cf:close()
    end
end

-- ============================================================
-- Locate whisper-cli and GGML models
-- ============================================================
local function findWhisperComponents()
    local cacheFile = os.getenv("TEMP") .. "\\autocaption_cli_path.txt"
    local path = getCachedPath(cacheFile)
    if path then return path end

    -- Ask user to select manually on the first run
    showMessage("AutoCaption", "First-time setup: Please select the whisper-cli.exe executable file from your application bin folder.", false)
    local selected = pickFile("whisper-cli.exe|whisper-cli.exe", "Select whisper-cli.exe")
    if selected then
        setCachedPath(cacheFile, selected)
        return selected
    end

    return nil
end

local function getModelPath(modelsDir)
    local cacheFile = os.getenv("TEMP") .. "\\autocaption_model_path.txt"
    local path = getCachedPath(cacheFile)
    if path then return path end

    showMessage("AutoCaption", "First-time setup: Please select the GGML Whisper model (.bin) file you want to use.", false)
    local selected = pickFile("GGML Model (*.bin)|*.bin", "Select GGML Whisper Model (.bin)", modelsDir)
    if selected then
        setCachedPath(cacheFile, selected)
        return selected
    end
    return nil
end

local function findFFmpeg(whisperExe)
    local binDir = whisperExe:match("(.*[/\\])")
    local path1 = binDir .. "ffmpeg.exe"
    local path2 = binDir .. "..\\ffmpeg.exe"
    local path3 = binDir .. "..\\..\\ffmpeg.exe"
    
    if fileExists(path1) then return path1 end
    if fileExists(path2) then return path2 end
    if fileExists(path3) then return path3 end
    return "ffmpeg.exe" -- default fallback to system PATH
end

-- ============================================================
-- Transcribe execution
-- ============================================================
local function runTranscribe(inputPath, outputSrtPath, whisperExe, modelPath, modelsDir)
    local ffmpegExe = findFFmpeg(whisperExe)
    local tempWavPath = os.getenv("TEMP") .. "\\autocaption_temp_audio.wav"
    
    -- 1. Extract audio to 16kHz mono WAV using FFmpeg
    local ffmpegCmd
    if isWindows then
        ffmpegCmd = string.format('""%s" -y -i "%s" -vn -acodec pcm_s16le -ar 16000 -ac 1 "%s""',
            ffmpegExe, inputPath, tempWavPath)
    else
        ffmpegCmd = string.format('"%s" -y -i "%s" -vn -acodec pcm_s16le -ar 16000 -ac 1 "%s"',
            ffmpegExe, inputPath, tempWavPath)
    end
    
    print("Running FFmpeg audio extraction: " .. ffmpegCmd)
    local fHandle = io.popen(ffmpegCmd .. " 2>&1")
    local fOutput = fHandle and fHandle:read("*a") or ""
    if fHandle then fHandle:close() end
    print(fOutput)

    if not fileExists(tempWavPath) then
        print("Error: FFmpeg audio extraction failed.")
        return false
    end

    -- 2. Detect and configure VAD flags (only use if ggml-silero-vad.bin is present)
    local vadModelPath = modelsDir .. "\\ggml-silero-vad.bin"
    local vadFlags = ""
    if fileExists(vadModelPath) then
        vadFlags = string.format('--vad -vm "%s"', vadModelPath)
    else
        print("VAD model ggml-silero-vad.bin not found. Running without VAD.")
    end

    -- 3. Run Whisper on the temporary WAV file
    local outPathWithoutExt = outputSrtPath:gsub("%.srt$", "")
    local whisperCmd
    if isWindows then
        whisperCmd = string.format('""%s" -m "%s" -osrt -of "%s" -l auto -t 4 -bs 5 -bo 5 -tp 0.0 -nf %s -f "%s""',
            whisperExe, modelPath, outPathWithoutExt, vadFlags, tempWavPath)
    else
        whisperCmd = string.format('"%s" -m "%s" -osrt -of "%s" -l auto -t 4 -bs 5 -bo 5 -tp 0.0 -nf %s -f "%s"',
            whisperExe, modelPath, outPathWithoutExt, vadFlags, tempWavPath)
    end
        
    print("Running Whisper C++ Engine: " .. whisperCmd)
    print("Processing audio - please wait...")

    local wHandle = io.popen(whisperCmd .. " 2>&1")
    local wOutput = wHandle and wHandle:read("*a") or ""
    if wHandle then wHandle:close() end

    print("---- Whisper C++ Console Output ----")
    print(wOutput)
    print("------------------------------------")
    
    -- Clean up temporary WAV
    os.remove(tempWavPath)
    
    return fileExists(outputSrtPath)
end

-- ============================================================
-- Import SRT into Media Pool + Timeline
-- ============================================================
local function importToMediaPool(srtPath)
    local projectManager = resolve:GetProjectManager()
    local project = projectManager and projectManager:GetCurrentProject()
    if not project then return false end

    local mediaPool = project:GetMediaPool()
    if not mediaPool then return false end

    local imported = mediaPool:ImportMedia({srtPath})
    if not imported or #imported == 0 then return false end

    local timeline = project:GetCurrentTimeline()
    if timeline then mediaPool:AppendToTimeline(imported) end
    return true
end

-- ============================================================
-- MAIN
-- ============================================================
local function Main()
    print("=== AutoCaption - Generate Captions (Local C++) ===")

    -- 1. Find Whisper components
    local whisperExe = findWhisperComponents()
    if not whisperExe then
        print("whisper-cli.exe not configured. Exiting.")
        return
    end
    
    local binDir = whisperExe:match("(.*[/\\])")
    local modelsDir = binDir .. "models"
    
    local modelPath = getModelPath(modelsDir)
    if not modelPath then
        print("GGML Model bin not selected. Exiting.")
        return
    end

    -- 2. Retrieve active clip from DaVinci Resolve Timeline (All-in-one workflow)
    local inputFile = nil
    local projectManager = resolve:GetProjectManager()
    local project = projectManager and projectManager:GetCurrentProject()
    local timeline = project and project:GetCurrentTimeline()
    
    if timeline then
        local currentItem = timeline:GetCurrentVideoItem()
        if currentItem then
            local mpItem = currentItem:GetMediaPoolItem()
            if mpItem then
                inputFile = mpItem:GetClipProperty("File Path")
                if not inputFile or inputFile == "" then
                    inputFile = mpItem:GetClipProperty("Location")
                end
            end
        end
    end

    -- Fallback to file dialog picker if timeline has no active selected clip at playhead
    if not inputFile or inputFile == "" then
        print("No active timeline clip found at playhead. Prompting file picker.")
        inputFile = pickFile()
    end

    if not inputFile or inputFile == "" then 
        print("No input media file selected. Exiting.")
        return 
    end
    
    print("Selected file: " .. inputFile)

    -- 3. Transcribe (output SRT next to input file)
    local srtPath = inputFile:gsub("%.%w+$", "") .. ".srt"

    local success = runTranscribe(inputFile, srtPath, whisperExe, modelPath, modelsDir)
    if not success then
        showMessage("AutoCaption", "Subtitle generation failed.\n\nSee DaVinci Resolve Console for details.", false)
        return
    end

    -- 4. Import to Media Pool
    if importToMediaPool(srtPath) then
        showMessage("AutoCaption", "SRT imported into Media Pool successfully!\n\nFile: " .. srtPath, false)
    else
        showMessage("AutoCaption", "SRT file created at:\n" .. srtPath ..
            "\n\nAutomatic import failed. Please drag it into Media Pool manually.", false)
    end
end

local ok, err = pcall(Main)
if not ok then print("Error: " .. tostring(err)) end