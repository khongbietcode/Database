function deleteUser(userId) {
    if (confirm('Bạn có chắc chắn muốn xóa người dùng này?')) {
        window.location.href = `/delete-user/${userId}/`;
    }
}