-- PSD por capas: arrastra imágenes encima del icono y te deja un PSD por capas al lado de cada una.

property engineDir : ""

on run
	set imgs to choose file with prompt "Elige una o varias imágenes (JPG o PNG) para sacar el PSD por capas:" of type {"public.jpeg", "public.png"} with multiple selections allowed
	processFiles(imgs)
end run

on open droppedItems
	processFiles(droppedItems)
end open

on processFiles(itemsList)
	set engineDir to (POSIX path of (path to home folder)) & "Library/Application Support/PSDporCapas/engine/"
	set total to count of itemsList
	set progress total steps to total
	set progress completed steps to 0
	set okList to {}
	set n to 0
	repeat with f in itemsList
		set n to n + 1
		set p to POSIX path of f
		set lowerP to do shell script "echo " & quoted form of p & " | tr '[:upper:]' '[:lower:]'"
		if not (lowerP ends with ".png" or lowerP ends with ".jpg" or lowerP ends with ".jpeg") then
			display notification "Solo JPG o PNG: " & (do shell script "basename " & quoted form of p) with title "PSD por capas"
		else
			set fname to do shell script "basename " & quoted form of p
			set statusFile to do shell script "mktemp -t psdcapas"
			set progress description to "PSD por capas · " & n & " de " & total & " · " & fname
			set progress additional description to "Empezando…"
			do shell script "nohup " & quoted form of (engineDir & "psdcapas.sh") & " " & quoted form of p & " " & quoted form of statusFile & " >/dev/null 2>&1 &"
			set stTxt to ""
			set t0 to current date
			repeat
				delay 2
				try
					set stTxt to do shell script "cat " & quoted form of statusFile
				end try
				if stTxt starts with "FIN|" then exit repeat
				if stTxt is not "" then
					set mins to ((current date) - t0) div 60
					set progress additional description to stTxt & "  (" & mins & " min)"
				end if
			end repeat
			do shell script "rm -f " & quoted form of statusFile
			set AppleScript's text item delimiters to "|"
			set parts to text items of stTxt
			set AppleScript's text item delimiters to ""
			set kind to item 2 of parts
			if kind is "OK" then
				set end of okList to item 3 of parts
				display notification fname & " → " & (item 4 of parts) with title "PSD listo" sound name "Glass"
			else if kind is "REVISAR" then
				set end of okList to item 3 of parts
				display dialog "El PSD de " & fname & " está hecho, pero conviene revisar:" & return & return & (item 4 of parts) & return & return & "Al lado tienes una hoja con todas las capas (_revision.png)." buttons {"Vale"} default button 1 with title "PSD por capas" with icon caution
			else
				set msg to item 3 of parts
				if msg is "LOGIN" then
					display dialog "Claude Code no tiene la sesión iniciada en este Mac." & return & return & "Pulsa «Iniciar sesión», entra con TU cuenta de Claude en la ventana que se abre y vuelve a arrastrar la imagen." buttons {"Cancelar", "Iniciar sesión"} default button 2 with title "PSD por capas" with icon caution
					if button returned of result is "Iniciar sesión" then
						tell application "Terminal"
							activate
							do script "export PATH=\"$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH\"; clear; echo 'Inicia sesión con tu cuenta de Claude. Cuando termine, cierra esta ventana.'; claude auth login"
						end tell
					end if
					return
				else
					display dialog "No se ha podido sacar el PSD de " & fname & ":" & return & return & msg buttons {"Vale"} default button 1 with title "PSD por capas" with icon stop
				end if
			end if
		end if
		set progress completed steps to n
	end repeat
	if (count of okList) > 0 then
		set lastPsd to item -1 of okList
		do shell script "open -R " & quoted form of lastPsd
	end if
end processFiles
