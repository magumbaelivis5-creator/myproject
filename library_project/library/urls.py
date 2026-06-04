from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('', views.home, name='home'),
    path('books/', views.book_list, name='book_list'),
    path('books/<int:pk>/', views.book_detail, name='book_detail'),

    # Auth
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # Member
    path('dashboard/', views.dashboard, name='dashboard'),
    path('borrow/<int:pk>/', views.borrow_book, name='borrow_book'),
    path('return/<int:record_id>/', views.return_book, name='return_book'),
    path('reserve/<int:pk>/', views.reserve_book, name='reserve_book'),
    path('cancel-reservation/<int:res_id>/', views.cancel_reservation, name='cancel_reservation'),
    path('profile/', views.profile, name='profile'),

    # Librarian
    path('librarian/', views.librarian_dashboard, name='librarian_dashboard'),
    path('books/add/', views.add_book, name='add_book'),
    path('books/<int:pk>/edit/', views.edit_book, name='edit_book'),
    path('books/<int:pk>/delete/', views.delete_book, name='delete_book'),
    path('categories/', views.manage_categories, name='manage_categories'),
    path('categories/<int:pk>/delete/', views.delete_category, name='delete_category'),
    path('all-borrows/', views.all_borrows, name='all_borrows'),
]
