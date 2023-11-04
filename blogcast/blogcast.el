;; -*- lexical-binding:t -*-
(require 'json)
(require 'cl)
(require 'request)

(define-derived-mode blogcast-mode fundamental-mode "BLOGCAST"
  "Majorish mode for working with the blogcast module")

(defgroup blogcast nil
  "The Blogcast AI-assisted blog reading tool")

(defcustom blogcast-server "http://192.168.0.12:8080"
  "Server URL to hit with requests for catwalk operations"
  :type 'string
  :group 'blogcast)

(defvar bc-sep " -=- ")

(defun bc-asc (key list)
  (cdr (assoc key list)))

(defun bc-alist<-plist (plist)
  (cl-loop for (key value . rest) on plist by 'cddr
           collect (cons key value)))

(defun blogcast-fname<-line-ix+url (line-ix url)
  (format "%06.0f-%s.%s" line-ix (file-name-base url) (file-name-extension url)))

(defun blogcast-insert-line (updated played url fname voice text)
  (insert (if updated "|" "."))
  (insert (if played "|" "."))
  (insert bc-sep)
  (insert (string-join (list url fname voice text) bc-sep))
  (newline))

(defun blogcast-parse-line (ln)
  (let* ((split (split-string ln bc-sep))
	 (flags (first split)))
    (list :updated (char-equal ?| (aref flags 0))
	  :played (char-equal ?| (aref flags 1))
	  :url (second split)
	  :file (nth 2 split)
	  :voice (nth 3 split)
	  :text (nth 4 split))))

(defun blogcast-parse-silence (ln)
  (string-to-number (second (split-string ln " "))))

(defun blogcast-current-line ()
  (interactive)
  (let* ((ln (buffer-substring (line-beginning-position) (line-end-position))))
    (if (string-match "^SILENCE" ln)
	nil
      (blogcast-parse-line ln))))

(defun blogcast-to-plists ()
  (let ((counter -1))
    (mapcar
     (lambda (ln)
       (cl-incf counter)
       (if (string-match "^SILENCE" ln)
	   (list :silence (blogcast-parse-silence ln))
	 (let* ((parsed (blogcast-parse-line ln)))
	   (list :url (cl-getf parsed :url) :file (cl-getf parsed :file) :voice (cl-getf parsed :voice) :text (cl-getf parsed :text)))))
     (seq-filter
      (lambda (ln) (> (length ln) 0))
      (split-string (buffer-string) "\n")))))

(defun blogcast-to-json ()
  (json-encode (mapcar #'bc-alist<-plist (blogcast-to-plists))))

(defun blogcast-write ()
  (write-file "result.blogc")
  (blogcast-mode)
  (hl-line-mode))

(defun blogcast-open-reading (file)
  (interactive "fReading: ")
  (if (string-match ".blogc$" file)
      (find-file file)
    (let ((blogc (format "%s.blogc" (file-name-sans-extension file))))
      (if (file-exists-p blogc)
	  (find-file blogc)
	(let ((full-json (json-read-file file)))
	  (let ((voice (bc-asc 'voice full-json))
		(results (bc-asc 'result full-json)))
	    (message (format "DOING THE THING %s %s %s" (length results) voice file))
	    (switch-to-buffer (format "blogcast--%s" (file-name-base (string-trim-right (file-name-parent-directory file) "/"))))
	    (cd (file-name-directory file))
	    (mapc
	     (lambda (el)
	       (message "PROCESSING LINE")
	       (if (assoc 'url el)
		   (let* ((url (bc-asc 'url el))
			  (fname (blogcast-fname<-line-ix+url (- (line-number-at-pos) 1) url)))
		     (blogcast-insert-line t nil url fname voice (bc-asc 'text el)))
		 (progn (insert (format "SILENCE %s" (bc-asc 'silence el)))
			(newline))))
	     results))))))
  (blogcast-write)
  (goto-char (point-min)))

(defvar *blogcast-play-proc* nil)

(defun blogcast-play (file)
  (interactive "fAudio: ")
  (when *blogcast-play-proc*
    (delete-process *blogcast-play-proc*)
    (setq *blogcast-play-proc* nil))
  (setq *blogcast-play-proc*
	(start-process "mplayer" nil "mplayer" file))
  (let ((ln (blogcast-current-line)))
    (kill-whole-line)
    (save-excursion
      (blogcast-insert-line (cl-getf ln :updated) t (cl-getf ln :url) (cl-getf ln :file) (cl-getf ln :voice) (cl-getf ln :text))
      (blogcast-write)))
  nil)

(defun blogcast-play-current-line ()
  (interactive)
  (if-let ((ln (blogcast-current-line)))
      (let ((fname (cl-getf ln :file)))
	(message (format "PLAYING -- %s" fname))
	(blogcast-play fname))))

(defun blogcast-request (endpoint method data on-success)
  (request (format "%s/%s" blogcast-server endpoint)
    :type method :data data
    :parser 'json-read
    :error (cl-function
	    (lambda (&rest args &key error-thrown &allow-other-keys)
	      (message "Got error: %S" error-thrown)))
    :success on-success))

(defun blogcast-health ()
  (interactive)
  (blogcast-request
   "health" "GET" nil
   (cl-function
    (lambda (&key data &allow-other-keys)
      (message (format "RECEIVED: %s" data))))))

(defun -bc-sub-port (port)
  (let ((p (format "%s" port)))
    (string-join
     (cl-concatenate
      'list
      (butlast (split-string blogcast-server ":"))
      (list p))
     ":")))

(defun blogcast-download-file (ln-number url port)
  (let ((fname (blogcast-fname<-line-ix+url (- ln-number 1) url))
	(full-url (format "%s%s" (if port (-bc-sub-port port) blogcast-server) url)))
    (async-shell-command (format "wget -O %s %s" fname full-url))
    fname))

(defun blogcast-re-record-current-line ()
  (interactive)
  (let* ((buf (current-buffer))
	 (ln-number (line-number-at-pos))
	 (ln (blogcast-current-line))
	 (line-voice (cl-getf ln :voice))
	 (line-text (cl-getf ln :text)))
    (save-excursion
      (kill-whole-line)
      (blogcast-insert-line nil nil (cl-getf ln :url) (cl-getf ln :file) line-voice line-text)
      (blogcast-write))
    (blogcast-request
     "v0/audio/tts" "POST" `(("text" . ,line-text) ("voice" . ,line-voice) ("k" . 1))
     (cl-function
      (lambda (&key data &allow-other-keys)
	(if (and (string= "ok" (bc-asc 'status data)))
	    (let ((url (aref (bc-asc 'urls data) 0)))
	      (with-current-buffer buf
		(save-excursion
		  (goto-line ln-number)
		  (let ((fname (blogcast-download-file ln-number url (bc-asc 'port data))))
		    (kill-whole-line)
		    (blogcast-insert-line t nil url fname line-voice (bc-asc 'text data))))
		(message (format "RECEIVED FILE: %s" url))))
	  (message (format "RE-RECORD FAILED: %s" data))))))))

(defun blogcast-edit-line ()
  (interactive)
  (let ((ln (blogcast-current-line)))
    (save-excursion
      (kill-whole-line)
      (blogcast-insert-line nil (cl-getf ln :played) (cl-getf ln :url) (cl-getf ln :file) (cl-getf ln :voice) (cl-getf ln :text))
      (blogcast-write))
    (beginning-of-line)
    (search-forward bc-sep)
    (search-forward bc-sep)
    (search-forward bc-sep)))

(defun blogcast-backward-line ()
  (interactive)
  (beginning-of-line)
  (backward-char)
  (beginning-of-line))

(defun blogcast-sound-info (fname)
  (interactive "fAudio: ")
  (mapcar
   (lambda (ln)
     (split-string ln "\s+:\s*"))
   (seq-filter
    (lambda (ln) (> (length ln) 0))
    (split-string
     (shell-command-to-string (format "sox --i %s" fname))
     "\n"))))

;; (Channels 1) (Sample Rate 24000)

(defun blogcast-silence (duration rate channels)
  (let ((fname (format "silence-%s.wav" duration)))
    (unless (file-exists-p fname)
      (message (shell-command-to-string (format "sox -n -r %s -c %s %s trim 0.0 %s" rate channels fname duration))))
    fname))

(defun blogcast-cat-script (script output)
  (let ((inputs (mapcar
		 (lambda (el)
		   (if (cl-getf el :silence)
		       (blogcast-silence (cl-getf el :silence) 24000 1)
		     (cl-getf el :file)))
		 script)))
    (shell-command-to-string (format "sox %s %s" (string-join inputs " ") output))))

(defun blogcast-save-cast (output)
  (interactive "sOutput: ")
  (blogcast-cat-script (blogcast-to-plists) (format "%s.wav" output))
  (async-shell-command (format "2ogg %s.wav" output)))

(defun blogcast-previous-unsynced ()
  (interactive)
  (beginning-of-line)
  (unless (re-search-backward "^\\." nil t)
    (goto-char (point-max))
    (re-search-backward "^\\.")))

(defun blogcast-next-unsynced ()
  (interactive)
  (unless (re-search-forward "^\\." nil t)
    (goto-char (point-min))
    (re-search-forward "^\\.")))

(defun blogcast-previous-unplayed ()
  (interactive)
  (beginning-of-line)
  (unless (re-search-backward "^.\\." nil t)
    (goto-char (point-max))
    (re-search-backward "^.\\.")))

(defun blogcast-next-unplayed ()
  (interactive)
  (unless (re-search-forward "^.\\." nil t)
    (goto-char (point-min))
    (re-search-forward "^.\\.")))

(defun blogcast-kill-line ()
  (interactive)
  (save-excursion
    (kill-whole-line)
    (insert "SILENCE 0.0\n")))

(defun blogcast-split-line ()
  (interactive)
  (let ((ln (blogcast-current-line)))
    (when ln
      (kill-line)
      (newline)
      (insert "SILENCE 0.5\n")
      (blogcast-insert-line nil nil (cl-getf ln :url) (cl-getf ln :file) (cl-getf ln :voice) (car kill-ring)))))

(define-key blogcast-mode-map (kbd "<return>") 'blogcast-play-current-line)
(define-key blogcast-mode-map (kbd "C-<down>") 'forward-line)
(define-key blogcast-mode-map (kbd "C-<up>") 'blogcast-backward-line)
(define-key blogcast-mode-map (kbd "C-c <return>") 'blogcast-re-record-current-line)
(define-key blogcast-mode-map (kbd "C-c <space>") 'blogcast-split-line)
(define-key blogcast-mode-map (kbd "C-<tab>") 'blogcast-edit-line)
(define-key blogcast-mode-map (kbd "C-c C-s") 'blogcast-save-cast)
(define-key blogcast-mode-map (kbd "C-M-p") 'blogcast-previous-unplayed)
(define-key blogcast-mode-map (kbd "C-M-n") 'blogcast-next-unplayed)
(define-key blogcast-mode-map (kbd "C-p") 'blogcast-previous-unsynced)
(define-key blogcast-mode-map (kbd "C-n") 'blogcast-next-unsynced)
(define-key blogcast-mode-map (kbd "C-k") 'blogcast-kill-line)

(provide 'blogcast-mode)
