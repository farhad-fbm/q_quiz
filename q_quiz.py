

import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import google.generativeai as genai
import json
import time
import threading
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# === CONFIGURE GEMINI ===
genai.configure(api_key="AIzaSyDe2fhOZTen8cGasIijZYdYhB5pqz6NRgY")  # Replace with your actual API key

# === QUIZ GENERATOR ===
def generate_quiz(topic):
    prompt = f"""
    You are a quiz generator. Generate exactly [new & different & not so easy] 3 multiple-choice quiz questions on the topic "{topic}".
    Each question should include:
    - A "question" string [single line]
    - An "options" list with exactly 4 items
    - An "answer" string (which must match one of the options)

    Respond ONLY in raw JSON in the following format:
    [
        {{
            "question": "What is 2+2?",
            "options": ["3", "4", "5", "6"],
            "answer": "4"
        }},
        ...
    ]
    """
    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content(prompt)
    try:
        text = response.text.strip()

        # Remove markdown code block formatting if present
        if text.startswith("```json"):
            text = text[7:]  # Remove ```json
        elif text.startswith("```"):
            text = text[3:]  # Remove ```
        if text.endswith("```"):
            text = text[:-3]

        print("Cleaned AI response:", text)
        return json.loads(text)
    except json.JSONDecodeError as e:
        print("JSON decode error:", e)
        return []

# === PDF GENERATOR ===
def generate_quiz_pdf(filename, topic, questions, user_answers, score, time_taken):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Title'],
        fontSize=16,
        spaceAfter=12
    )
    
    heading_style = ParagraphStyle(
        'Heading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=6
    )
    
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6
    )
    
    info_style = ParagraphStyle(
        'Info',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6,
        textColor=colors.darkblue
    )
    
    # Create the content
    content = []
    
    # Add title
    content.append(Paragraph(f"Quiz Review: {topic}", title_style))
    content.append(Spacer(1, 0.25*inch))
    
    # Add score and time info
    content.append(Paragraph(f"Score: {score}/{len(questions)}", heading_style))
    
    # Format time taken
    minutes = int(time_taken // 60)
    seconds = int(time_taken % 60)
    time_str = f"{minutes} min {seconds} sec" if minutes > 0 else f"{seconds} sec"
    content.append(Paragraph(f"Time taken: {time_str}", info_style))
    
    content.append(Spacer(1, 0.25*inch))
    
    # Add questions and answers
    for i, q in enumerate(questions):
        # Question
        content.append(Paragraph(f"Question {i+1}: {q['question']}", heading_style))
        
        # Options with highlighting
        data = []
        for opt in q['options']:
            if opt == q['answer'] and opt == user_answers[i]:
                # Correct answer and user selected it
                data.append([Paragraph(f"✓ {opt}", normal_style)])
            elif opt == q['answer']:
                # Correct answer but user didn't select it
                data.append([Paragraph(f"✓ {opt} (Correct answer)", normal_style)])
            elif opt == user_answers[i]:
                # User selected this but it's wrong
                data.append([Paragraph(f"✗ {opt} (Your answer)", normal_style)])
            else:
                # Other option
                data.append([Paragraph(opt, normal_style)])
        
        # Create table for options
        table = Table(data, colWidths=[5*inch])
        
        # Add table style with colors
        table_style = TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ])
        
        # Add color highlighting
        for row, opt in enumerate(q['options']):
            if opt == q['answer']:
                # Correct answer - green
                table_style.add('BACKGROUND', (0, row), (0, row), colors.lightgreen)
                table_style.add('TEXTCOLOR', (0, row), (0, row), colors.darkgreen)
            elif opt == user_answers[i] and opt != q['answer']:
                # User's incorrect answer - red
                table_style.add('BACKGROUND', (0, row), (0, row), colors.mistyrose)
                table_style.add('TEXTCOLOR', (0, row), (0, row), colors.darkred)
        
        table.setStyle(table_style)
        content.append(table)
        content.append(Spacer(1, 0.25*inch))
    
    # Build the PDF
    doc.build(content)

# === QUIZ APP CLASS ===
class QuizApp:
    def __init__(self, root, questions, parent_window, topic):
        self.root = root
        self.root.title("Q Quiz AI Edition")
        self.root.geometry("600x500")  # Made slightly taller for the download button
        
        self.parent_window = parent_window
        self.questions = questions
        self.topic = topic
        self.q_no = 0
        self.score = 0
        self.user_answers = [""] * len(questions)
        self.user_answer = tk.StringVar(value="")  # Initialize with empty string
        self.timer_running = True
        self.time_left = 60  # 60 seconds for all questions
        self.review_mode = False
        
        # Track time taken
        self.start_time = time.time()
        self.time_taken = 0
        
        self.create_widgets()
        self.display_question()
        self.start_timer()

    def create_widgets(self):
        # Top frame for timer, question tracking, and score
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=5)
        
        # Timer label
        self.timer_label = tk.Label(top_frame, text="Time left: 60s", font=("Arial", 12))
        self.timer_label.pack(side="left")
        
        # Score label (initially hidden)
        self.score_label = tk.Label(top_frame, text="", font=("Arial", 12, "bold"), fg="blue")
        self.score_label.pack(side="left", padx=20)
        
        # Time taken label (initially hidden)
        self.time_taken_label = tk.Label(top_frame, text="", font=("Arial", 12), fg="darkblue")
        self.time_taken_label.pack(side="left", padx=20)
        self.time_taken_label.pack_forget()  # Hide initially
        
        # Question tracking
        self.tracking_label = tk.Label(top_frame, text=f"Q: 1/{len(self.questions)}", font=("Arial", 12))
        self.tracking_label.pack(side="right")
        
        # Review mode indicator (initially hidden)
        self.review_label = tk.Label(top_frame, text="REVIEW MODE", font=("Arial", 12, "bold"), fg="purple")
        self.review_label.pack(side="right", padx=20)
        self.review_label.pack_forget()  # Hide initially
        
        # Question frame
        question_frame = tk.Frame(self.root)
        question_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.question_label = tk.Label(question_frame, text="", font=("Arial", 14), wraplength=550, justify="left")
        self.question_label.pack(pady=20, anchor="w")

        # Options frame
        options_frame = tk.Frame(question_frame)
        options_frame.pack(fill="both", expand=True)
        
        self.radio_buttons = []
        self.option_labels = []
        
        for i in range(4):
            option_frame = tk.Frame(options_frame)
            option_frame.pack(fill="x", pady=5, anchor="w")
            
            rb = tk.Radiobutton(option_frame, variable=self.user_answer, value="", font=("Arial", 12))
            rb.pack(side="left")
            self.radio_buttons.append(rb)
            
            label = tk.Label(option_frame, text="", font=("Arial", 12), wraplength=500, justify="left")
            label.pack(side="left", padx=5)
            self.option_labels.append(label)
        
        # Navigation buttons frame
        button_frame = tk.Frame(self.root)
        button_frame.pack(fill="x", padx=20, pady=10)
        
        self.prev_btn = tk.Button(button_frame, text="Previous", command=self.prev_question, width=10)
        self.prev_btn.pack(side="left", padx=5)
        
        self.next_btn = tk.Button(button_frame, text="Next", command=self.next_question, width=10)
        self.next_btn.pack(side="left", padx=5)
        
        self.submit_btn = tk.Button(button_frame, text="Submit", command=self.submit_quiz, width=10)
        self.submit_btn.pack(side="right", padx=5)
        
        self.gen_btn = tk.Button(button_frame, text="New Quiz", command=self.return_to_generator, width=10)
        self.gen_btn.pack(side="right", padx=5)
        
        # Download PDF button (initially hidden)
        self.download_frame = tk.Frame(self.root)
        self.download_frame.pack(fill="x", padx=20, pady=10)
        
        self.download_btn = tk.Button(
            self.download_frame, 
            text="Download Results as PDF", 
            command=self.download_pdf,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 12, "bold"),
            height=2
        )
        self.download_btn.pack(fill="x")
        self.download_frame.pack_forget()  # Hide initially

    def display_question(self):
        if self.q_no >= len(self.questions):
            return
            
        q = self.questions[self.q_no]
        self.question_label.config(text=f"{q['question']}")
        self.tracking_label.config(text=f"Q: {self.q_no + 1}/{len(self.questions)}")
        
        # Set the radio button value to the previously selected answer (if any)
        self.user_answer.set(self.user_answers[self.q_no])
        
        for i, opt in enumerate(q['options']):
            self.radio_buttons[i].config(value=opt)
            
            if self.review_mode:
                # In review mode, show correct/incorrect indicators
                if opt == q['answer']:
                    # Correct answer - green
                    self.option_labels[i].config(text=opt, fg="green")
                elif opt == self.user_answers[self.q_no] and opt != q['answer']:
                    # User's incorrect answer - red
                    self.option_labels[i].config(text=opt, fg="red")
                else:
                    # Other options - black
                    self.option_labels[i].config(text=opt, fg="black")
            else:
                # Normal mode
                self.option_labels[i].config(text=opt, fg="black")
                
                # Make the label clickable to select the radio button
                option_value = opt  # Store the value in a local variable for the lambda
                self.option_labels[i].bind("<Button-1>", lambda e, val=option_value: self.select_option(val))
                self.option_labels[i].config(cursor="hand2")  # Change cursor to hand when hovering
        
        # Update button states
        self.prev_btn.config(state="disabled" if self.q_no == 0 else "normal")
        
        if self.review_mode:
            self.next_btn.config(text="Next" if self.q_no < len(self.questions) - 1 else "Finish")
            self.submit_btn.config(state="disabled")
            # Unbind click events in review mode
            for label in self.option_labels:
                label.unbind("<Button-1>")
                label.config(cursor="")
        else:
            self.next_btn.config(text="Next")
            self.submit_btn.config(state="normal")
    
    def select_option(self, value):
        """Select the radio button when the label is clicked"""
        self.user_answer.set(value)

    def next_question(self):
        if not self.review_mode:
            # Save the current answer
            self.user_answers[self.q_no] = self.user_answer.get()
        
        if self.q_no < len(self.questions) - 1:
            self.q_no += 1
            self.display_question()
        elif self.review_mode:
            # In review mode, if we're at the last question, finish the quiz
            self.root.destroy()
            self.parent_window.deiconify()

    def prev_question(self):
        if not self.review_mode:
            # Save the current answer
            self.user_answers[self.q_no] = self.user_answer.get()
            
        if self.q_no > 0:
            self.q_no -= 1
            self.display_question()

    def submit_quiz(self):
        # Save the current answer
        self.user_answers[self.q_no] = self.user_answer.get()
        
        # Check if all questions are answered
        unanswered = [i+1 for i, ans in enumerate(self.user_answers) if not ans]
        if unanswered:
            messagebox.showwarning("Warning", f"Please answer question(s): {', '.join(map(str, unanswered))}")
            return
            
        # Stop the timer and calculate time taken
        self.timer_running = False
        self.time_taken = time.time() - self.start_time
        
        # Format time taken for display
        minutes = int(self.time_taken // 60)
        seconds = int(self.time_taken % 60)
        time_str = f"{minutes} min {seconds} sec" if minutes > 0 else f"{seconds} sec"
        
        # Calculate score
        self.score = 0
        for i, q in enumerate(self.questions):
            if self.user_answers[i] == q['answer']:
                self.score += 1
        
        # Show score in a message box
        # messagebox.showinfo("Quiz Completed", f"Your score: {self.score}/{len(self.questions)}\nTime taken: {time_str}")
        
        # Enter review mode
        self.review_mode = True
        
        # Show score and time taken in the UI
        self.score_label.config(text=f"Score: {self.score}/{len(self.questions)}")
        self.time_taken_label.config(text=f"Time: {time_str}")
        
        # Hide timer and show review mode indicator and time taken
        self.timer_label.pack_forget()
        self.review_label.pack(side="left")
        self.time_taken_label.pack(side="left")
        
        # Show download button
        self.download_frame.pack(fill="x", padx=20, pady=10)
        
        self.q_no = 0  # Start review from the first question
        self.display_question()

    def download_pdf(self):
        """Generate and download a PDF with quiz results"""
        try:
            # Ask user where to save the PDF
            file_path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                title="Save Quiz Results"
            )
            
            if not file_path:  # User cancelled
                return
                
            # Generate the PDF
            generate_quiz_pdf(
                file_path, 
                self.topic, 
                self.questions, 
                self.user_answers, 
                self.score,
                self.time_taken  # Pass time taken to PDF generator
            )
            
            messagebox.showinfo("Success", f"Quiz results saved to {file_path}")
            
            # Try to open the PDF
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(file_path)
                elif os.name == 'posix':  # macOS or Linux
                    import subprocess
                    subprocess.call(('open', file_path) if os.name == 'darwin' else ('xdg-open', file_path))
            except:
                pass  # Silently fail if we can't open the PDF
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate PDF: {str(e)}")

    def start_timer(self):
        def update_timer():
            while self.timer_running and self.time_left > 0:
                time.sleep(1)
                self.time_left -= 1
                self.timer_label.config(text=f"Time left: {self.time_left}s")
                
            if self.time_left <= 0 and self.timer_running:
                self.timer_running = False
                messagebox.showinfo("Time's Up!", "Your time is up! Submitting quiz...")
                self.root.after(0, self.submit_quiz)
        
        timer_thread = threading.Thread(target=update_timer)
        timer_thread.daemon = True
        timer_thread.start()

    def return_to_generator(self):
        self.timer_running = False
        self.root.destroy()
        self.parent_window.deiconify()

# === MAIN MENU TO SELECT TOPIC ===
class QuizGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Q Quiz AI")
        self.root.geometry("400x200")
        
        tk.Label(root, text="Enter Quiz Topic:", font=("Arial", 12)).pack(pady=10)
        self.topic_entry = tk.Entry(root, font=("Arial", 12))
        self.topic_entry.pack(pady=5)
        
        self.start_btn = tk.Button(root, text="Generate Quiz", command=self.start_quiz, font=("Arial", 12))
        self.start_btn.pack(pady=20)

    def start_quiz(self):
        topic = self.topic_entry.get().strip()
        if not topic:
            messagebox.showwarning("Input needed", "Please enter a topic.")
            return

        self.start_btn.config(state="disabled")
        self.root.update()
        
        questions = generate_quiz(topic)
        if not questions:
            messagebox.showerror("Error", "Failed to load quiz from AI.")
            self.start_btn.config(state="normal")
            return

        # Hide the main window
        self.root.withdraw()
        
        # Open quiz window
        quiz_window = tk.Toplevel(self.root)
        QuizApp(quiz_window, questions, self.root, topic)
        self.start_btn.config(state="normal")

# === MAIN ===
if __name__ == "__main__":
    root = tk.Tk()
    app = QuizGenerator(root)
    root.mainloop()