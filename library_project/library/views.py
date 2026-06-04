from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from .models import Book, Category, BorrowRecord, Reservation, UserProfile
from .forms import (
    UserRegisterForm, UserProfileForm, BookForm, BorrowForm,
    SearchForm, CategoryForm
)


def is_librarian(user):
    return user.is_staff or user.is_superuser


# ── Public Views ────────────────────────────────────────────────────────────

def home(request):
    recent_books = Book.objects.select_related('category').order_by('-date_added')[:8]
    categories = Category.objects.all()
    total_books = Book.objects.count()
    available_books = Book.objects.filter(available_copies__gt=0).count()
    ctx = {
        'recent_books': recent_books,
        'categories': categories,
        'total_books': total_books,
        'available_books': available_books,
    }
    return render(request, 'library/home.html', ctx)


def book_list(request):
    books = Book.objects.select_related('category').all()
    form = SearchForm(request.GET or None)
    if form.is_valid():
        q = form.cleaned_data.get('query')
        category_id = form.cleaned_data.get('category')
        available_only = form.cleaned_data.get('available_only')
        if q:
            books = books.filter(
                Q(title__icontains=q) | Q(author__icontains=q) | Q(isbn__icontains=q)
            )
        if category_id:
            books = books.filter(category_id=category_id)
        if available_only:
            books = books.filter(available_copies__gt=0)
    categories = Category.objects.all()
    return render(request, 'library/book_list.html', {
        'books': books, 'form': form, 'categories': categories
    })


def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    user_has_active_borrow = False
    user_has_reservation = False
    if request.user.is_authenticated:
        user_has_active_borrow = BorrowRecord.objects.filter(
            user=request.user, book=book, status__in=['borrowed', 'overdue']
        ).exists()
        user_has_reservation = Reservation.objects.filter(
            user=request.user, book=book, status='active'
        ).exists()
    return render(request, 'library/book_detail.html', {
        'book': book,
        'user_has_active_borrow': user_has_active_borrow,
        'user_has_reservation': user_has_reservation,
    })


# ── Auth Views ───────────────────────────────────────────────────────────────

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(user=user)
            login(request, user)
            messages.success(request, 'Account created! Welcome to the library.')
            return redirect('home')
    else:
        form = UserRegisterForm()
    return render(request, 'library/register.html', {'form': form})


def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect(request.GET.get('next', 'home'))
        messages.error(request, 'Invalid username or password.')
    return render(request, 'library/login.html')


def user_logout(request):
    logout(request)
    return redirect('home')


# ── Member Views ─────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    borrows = BorrowRecord.objects.filter(user=request.user).select_related('book').order_by('-borrow_date')[:10]
    reservations = Reservation.objects.filter(user=request.user, status='active').select_related('book')
    overdue = BorrowRecord.objects.filter(user=request.user, status='overdue')
    return render(request, 'library/dashboard.html', {
        'borrows': borrows,
        'reservations': reservations,
        'overdue_count': overdue.count(),
    })


@login_required
def borrow_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if not book.is_available:
        messages.error(request, 'No copies available right now.')
        return redirect('book_detail', pk=pk)
    already = BorrowRecord.objects.filter(
        user=request.user, book=book, status__in=['borrowed', 'overdue']
    ).exists()
    if already:
        messages.error(request, 'You already have this book borrowed.')
        return redirect('book_detail', pk=pk)
    due_date = timezone.now() + timezone.timedelta(days=14)
    BorrowRecord.objects.create(user=request.user, book=book, due_date=due_date)
    book.available_copies -= 1
    book.save()
    # Fulfil reservation if exists
    Reservation.objects.filter(user=request.user, book=book, status='active').update(status='fulfilled')
    messages.success(request, f'You borrowed "{book.title}". Due back in 14 days.')
    return redirect('dashboard')


@login_required
def return_book(request, record_id):
    record = get_object_or_404(BorrowRecord, pk=record_id, user=request.user)
    if record.status == 'returned':
        messages.info(request, 'This book is already returned.')
        return redirect('dashboard')
    record.status = 'returned'
    record.return_date = timezone.now()
    record.save()
    record.book.available_copies += 1
    record.book.save()
    messages.success(request, f'"{record.book.title}" returned successfully.')
    return redirect('dashboard')


@login_required
def reserve_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    already = Reservation.objects.filter(user=request.user, book=book, status='active').exists()
    if already:
        messages.error(request, 'You already have an active reservation for this book.')
        return redirect('book_detail', pk=pk)
    Reservation.objects.create(user=request.user, book=book)
    messages.success(request, f'Reserved "{book.title}". We\'ll notify you when available.')
    return redirect('dashboard')


@login_required
def cancel_reservation(request, res_id):
    reservation = get_object_or_404(Reservation, pk=res_id, user=request.user)
    reservation.status = 'cancelled'
    reservation.save()
    messages.success(request, 'Reservation cancelled.')
    return redirect('dashboard')


@login_required
def profile(request):
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile_obj)
    return render(request, 'library/profile.html', {'form': form, 'profile': profile_obj})


# ── Librarian / Admin Views ──────────────────────────────────────────────────

@login_required
@user_passes_test(is_librarian)
def librarian_dashboard(request):
    total_books = Book.objects.count()
    total_users = User.objects.count()
    active_borrows = BorrowRecord.objects.filter(status__in=['borrowed', 'overdue']).count()
    overdue = BorrowRecord.objects.filter(status='overdue').select_related('user', 'book')
    recent_borrows = BorrowRecord.objects.select_related('user', 'book').order_by('-borrow_date')[:10]
    return render(request, 'library/librarian_dashboard.html', {
        'total_books': total_books,
        'total_users': total_users,
        'active_borrows': active_borrows,
        'overdue': overdue,
        'recent_borrows': recent_borrows,
    })


@login_required
@user_passes_test(is_librarian)
def add_book(request):
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Book added successfully.')
            return redirect('book_list')
    else:
        form = BookForm()
    return render(request, 'library/book_form.html', {'form': form, 'action': 'Add'})


@login_required
@user_passes_test(is_librarian)
def edit_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, 'Book updated.')
            return redirect('book_detail', pk=pk)
    else:
        form = BookForm(instance=book)
    return render(request, 'library/book_form.html', {'form': form, 'action': 'Edit', 'book': book})


@login_required
@user_passes_test(is_librarian)
def delete_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        book.delete()
        messages.success(request, 'Book deleted.')
        return redirect('book_list')
    return render(request, 'library/confirm_delete.html', {'book': book})


@login_required
@user_passes_test(is_librarian)
def manage_categories(request):
    categories = Category.objects.all()
    form = CategoryForm()
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category added.')
            return redirect('manage_categories')
    return render(request, 'library/manage_categories.html', {'categories': categories, 'form': form})


@login_required
@user_passes_test(is_librarian)
def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Category deleted.')
    return redirect('manage_categories')


@login_required
@user_passes_test(is_librarian)
def all_borrows(request):
    borrows = BorrowRecord.objects.select_related('user', 'book').all()
    return render(request, 'library/all_borrows.html', {'borrows': borrows})
