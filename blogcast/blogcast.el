;; -*- lexical-binding:t -*-
(require 'json)
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

(defun blogcast-fname<-line-ix+url (line-ix url)
  (format "%06.0f-%s.%s" line-ix (file-name-base url) (file-name-extension url)))

(defun blogcast-insert-line (updated played url text)
  (insert (if updated "|" "."))
  (insert (if played "|" "."))
  (insert bc-sep)
  (insert url)
  (insert bc-sep)
  (insert text)
  (newline))

(defun blogcast-parse-line (ln)
  (let* ((split (split-string ln bc-sep))
	 (flags (first split)))
    (list :updated (char-equal ?| (aref flags 0))
	  :played (char-equal ?| (aref flags 1))
	  :url (second split)
	  :text (nth 2 split))))

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
	 (let* ((parsed (blogcast-parse-line ln))
		(url (cl-getf parsed :url))
		(fname (blogcast-fname<-line-ix+url counter url)))
	   (list :url url :file fname :text (cl-getf parsed :text)))))
     (seq-filter
      (lambda (ln) (> (length ln) 0))
      (split-string (buffer-string) "\n")))))

(defun blogcast-to-json ()
  ;; TODO - factor out the common stuff between this and the plists
  (json-encode
   (let ((counter -1))
     (mapcar
      (lambda (ln)
	(cl-incf counter)
	(if (string-match "^SILENCE" ln)
	    `(("silence" . ,(blogcast-parse-silence ln)))
	  ;; (list :silence (blogcast-parse-silence ln))
	  (let* ((parsed (blogcast-parse-line ln))
		 (url (cl-getf parsed :url))
		 (fname (blogcast-fname<-line-ix+url counter url)))
	    (list :url url :file fname :text (cl-getf parsed :text))
	    `(("url" . ,url)
	      ("file" . ,fname)
	      ("text" . ,(cl-getf parsed :text))))))
      (seq-filter
       (lambda (ln) (> (length ln) 0))
       (split-string (buffer-string) "\n"))))))

(defun blogcast-open-reading (file)
  (interactive "fReading: ")
  (let ((blogc (format "%s.blogc" (file-name-sans-extension file))))
    (if (file-exists-p blogc)
	(find-file blogc)
      (let* ((full-json (json-read-file file))
	     (result (bc-asc 'result full-json)))
	(switch-to-buffer (format "blogcast--%s" (file-name-base (string-trim-right (file-name-parent-directory file) "/"))))
	(cd (file-name-directory file))
	(mapc
	 (lambda (pair)
	   (if (assoc 'url pair)
	       (blogcast-insert-line t nil (bc-asc 'url pair) (bc-asc 'text pair))
	     (progn (insert (format "SILENCE %s" (bc-asc 'silence pair)))
		    (newline))))
	 result)))
    (blogcast-mode)
    (hl-line-mode)
    (goto-char (point-min))))

(defun blogcast-play (file)
  (interactive "fAudio: ")
  (shell-command-to-string (format "mplayer %s" file))
  (let ((ln (blogcast-current-line)))
    (kill-whole-line)
    (save-excursion
      (blogcast-insert-line (cl-getf ln :updated) t (cl-getf ln :url) (cl-getf ln :text))))
  nil)

(defun blogcast-play-current-line ()
  (interactive)
  (if-let ((ln (blogcast-current-line)))
      (let* ((url (cl-getf ln :url))
	     (fname (blogcast-fname<-line-ix+url (- (line-number-at-pos) 1) url)))
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

(defun blogcast-download-file (ln-number url)
  (let ((fname (blogcast-fname<-line-ix+url (- ln-number 1) url)))
    (shell-command (format "wget -O %s %s%s" fname blogcast-server url))
    fname))

(defun blogcast-re-record-current-line ()
  (interactive)
  (let* ((ln-number (line-number-at-pos))
	 (ln (blogcast-current-line))
	 (line-text (cl-getf ln :text)))
    (save-excursion
      (kill-whole-line)
      (blogcast-insert-line nil nil (cl-getf ln :url) line-text))
    (blogcast-request
     "v0/audio/tts" "POST" `(("text" . ,line-text) ("voice" . "leo") ("k" . 1))
     (cl-function
      (lambda (&key data &allow-other-keys)
	(if (string= "ok" (bc-asc 'status data))
	    (let ((url (aref (bc-asc 'urls data) 0))
		  (text (bc-asc 'text data)))
	      (save-excursion
		(goto-line ln-number)
		(blogcast-download-file ln-number url)
		(kill-whole-line)
		(blogcast-insert-line t nil url text))
	      (message (format "RECEIVED FILE: %s" url)))
	  (message (format "RE-RECORD FAILED: %s" data))))))))

(defun blogcast-edit-line ()
  (interactive)
  (let ((ln (blogcast-current-line)))
    (save-excursion
      (kill-whole-line)
      (blogcast-insert-line nil (cl-getf ln :played) (cl-getf ln :url) (cl-getf ln :text)))
    (beginning-of-line)
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
  (blogcast-cat-script (blogcast-to-plists) (format "%s.wav" output)))

(define-key blogcast-mode-map (kbd "<return>") 'blogcast-play-current-line)
(define-key blogcast-mode-map (kbd "C-<down>") 'forward-line)
(define-key blogcast-mode-map (kbd "C-<up>") 'blogcast-backward-line)
(define-key blogcast-mode-map (kbd "C-c <return>") 'blogcast-re-record-current-line)
(define-key blogcast-mode-map (kbd "C-<tab>") 'blogcast-edit-line)
(define-key blogcast-mode-map (kbd "C-c C-s") 'blogcast-save-cast)

(provide 'blogcast-mode)
