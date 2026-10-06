let studentsData = [];
let facultyData = [];
let collegesData = [];
let collegeRequestsData = [];
let departmentRequestId = 0;
let classRequestId = 0;
let managedDepartmentRequestId = 0;


// ==================================================
// ESCAPE HTML
// ==================================================

function escapeHtml(value) {

    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

}

async function loadStudentClasses() {
    const collegeSelect = document.getElementById("userCollege");
    const classSelect = document.getElementById("studentClass");
    const classHelp = document.getElementById("studentClassHelp");
    const requestId = ++classRequestId;
    const college = collegesData.find(function (item) {
        return item.code === collegeSelect.value;
    });

    classSelect.disabled = true;
    classSelect.innerHTML = "<option value=''>Loading classes...</option>";

    if (!college) {
        classSelect.innerHTML = "<option value=''>Select an approved college first</option>";
        classHelp.textContent = "Select a class belonging to the chosen college.";
        return;
    }

    try {
        const query = new URLSearchParams({ college_id: String(college.id) });
        const response = await fetch("/api/classes?" + query.toString());
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || "Unable to load classes.");
        }
        if (requestId !== classRequestId) return;

        const classes = result.classes || [];
        classSelect.replaceChildren();
        if (!classes.length) {
            const option = document.createElement("option");
            option.value = "";
            option.textContent = "No classes available";
            classSelect.appendChild(option);
            classHelp.textContent = "Create a course and class before adding a student.";
            return;
        }

        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Select Class";
        classSelect.appendChild(placeholder);
        classes.forEach(function (item) {
            const option = document.createElement("option");
            option.value = String(item.id);
            option.textContent = [
                item.course,
                "Year " + item.year_level,
                "Semester " + item.semester,
                item.division,
                item.academic_year
            ].filter(Boolean).join(" · ");
            classSelect.appendChild(option);
        });
        classSelect.disabled = false;
        classHelp.textContent = "Select the student's class within the chosen college.";
    } catch (error) {
        if (requestId !== classRequestId) return;
        classSelect.innerHTML = "<option value=''>Unable to load classes</option>";
        classHelp.textContent = error.message || "Unable to load classes.";
    }
}


// ==================================================
// ESCAPE VALUE
// ==================================================

function escapeValue(value) {

    return String(value ?? "")
        .replace(/\\/g, "\\\\")
        .replace(/'/g, "\\'");

}

function updateStudentClassFields() {
    const isStudent = document.getElementById("userRole").value === "student";
    const group = document.getElementById("studentClassGroup");
    const classSelect = document.getElementById("studentClass");
    const rollInput = document.getElementById("studentRollNumber");

    group.style.display = isStudent ? "block" : "none";
    classSelect.required = isStudent;
    rollInput.required = isStudent;

    if (isStudent) {
        loadStudentClasses();
    } else {
        classRequestId += 1;
        classSelect.disabled = true;
        classSelect.innerHTML = "<option value=''>Select a college and student role first</option>";
    }
}


// ==================================================
// LOAD COLLEGES
// ==================================================

async function loadColleges() {

    const collegeSelect =
        document.getElementById("userCollege");
    const departmentCollegeSelect =
        document.getElementById("departmentCollege");

    if (!collegeSelect) return;

    try {

        const response =
            await fetch("/api/colleges");

        if (!response.ok) {

            throw new Error(
                "College API error: " + response.status
            );

        }

        collegesData =
            await response.json();

        collegeSelect.innerHTML = `
            <option value="">
                Select College
            </option>
        `;


        collegesData.forEach(function (college) {

            collegeSelect.innerHTML += `
                <option value="${escapeHtml(college.code)}">
                    ${escapeHtml(college.name)}
                    (${escapeHtml(college.code)})
                </option>
            `;

        });

        if (departmentCollegeSelect) {
            departmentCollegeSelect.innerHTML = `
                <option value="">Select College</option>
            `;

            collegesData.forEach(function (college) {
                departmentCollegeSelect.innerHTML += `
                    <option value="${escapeHtml(college.code)}">
                        ${escapeHtml(college.name)}
                        (${escapeHtml(college.code)})
                    </option>
                `;
            });
        }

        collegeSelect.innerHTML += `
            <option value="OTHER">
                Other College — Request Registration
            </option>
        `;

    }

    catch (error) {

        console.error(
            "College Error:",
            error
        );

        collegeSelect.innerHTML = `
            <option value="">
                Unable to load colleges
            </option>
        `;
        if (departmentCollegeSelect) {
            departmentCollegeSelect.innerHTML = `
                <option value="">Unable to load colleges</option>
            `;
        }

    }

}


async function loadFacultyDepartments() {

    const collegeSelect = document.getElementById("userCollege");
    const departmentSelect = document.getElementById("facultyDepartment");
    const departmentHelp = document.getElementById("facultyDepartmentHelp");
    const requestId = ++departmentRequestId;
    const collegeCode = collegeSelect.value;

    departmentSelect.disabled = true;
    departmentSelect.innerHTML = "<option value=''>Loading departments...</option>";

    if (!collegeCode || collegeCode === "OTHER") {
        departmentSelect.innerHTML = "<option value=''>Select an approved college first</option>";
        departmentHelp.textContent = "Select an active department belonging to the chosen college.";
        return;
    }

    try {
        const query = new URLSearchParams({ college_code: collegeCode });
        const response = await fetch("/api/departments?" + query.toString());
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || "Unable to load departments.");
        }
        if (requestId !== departmentRequestId) return;

        const departments = result.departments || [];
        departmentSelect.replaceChildren();

        if (!departments.length) {
            const option = document.createElement("option");
            option.value = "";
            option.textContent = "No active departments available";
            departmentSelect.appendChild(option);
            departmentHelp.textContent = "A faculty account cannot be created until this college has an active department.";
            return;
        }

        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Select Department";
        departmentSelect.appendChild(placeholder);

        departments.forEach(function (department) {
            const option = document.createElement("option");
            option.value = String(department.id);
            option.textContent = department.name + " (" + department.code + ")";
            departmentSelect.appendChild(option);
        });

        departmentSelect.disabled = false;
        departmentHelp.textContent = "Select an active department belonging to the chosen college.";
    } catch (error) {
        if (requestId !== departmentRequestId) return;
        departmentSelect.innerHTML = "<option value=''>Unable to load departments</option>";
        departmentHelp.textContent = error.message || "Unable to load departments.";
    }
}


async function loadManagedDepartments() {

    const requestId = ++managedDepartmentRequestId;
    const collegeCode =
        document.getElementById("departmentCollege").value;
    const tableBody =
        document.getElementById("departmentsTableBody");

    if (!collegeCode) {
        tableBody.innerHTML = `
            <tr><td colspan="3">Select a college to view departments.</td></tr>
        `;
        return;
    }

    tableBody.innerHTML = `
        <tr><td colspan="3">Loading departments...</td></tr>
    `;

    try {
        const query = new URLSearchParams({
            college_code: collegeCode,
            include_inactive: "1"
        });
        const response = await fetch("/api/departments?" + query.toString());
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || "Unable to load departments.");
        }
        if (requestId !== managedDepartmentRequestId) return;

        const departments = result.departments || [];
        if (!departments.length) {
            tableBody.innerHTML = `
                <tr><td colspan="3">No departments exist for this college.</td></tr>
            `;
            return;
        }

        tableBody.innerHTML = departments.map(function (department) {
            return `
                <tr>
                    <td>${escapeHtml(department.name)}</td>
                    <td>${escapeHtml(department.code)}</td>
                    <td>${department.is_active ? "Active" : "Inactive"}</td>
                </tr>
            `;
        }).join("");
    } catch (error) {
        if (requestId !== managedDepartmentRequestId) return;
        tableBody.innerHTML = `
            <tr><td colspan="3">${escapeHtml(error.message || "Unable to load departments.")}</td></tr>
        `;
    }
}


function updateFacultyDepartmentField() {

    const isFaculty =
        document.getElementById("userRole").value === "faculty";
    const group = document.getElementById("facultyDepartmentGroup");
    const departmentSelect = document.getElementById("facultyDepartment");

    group.style.display = isFaculty ? "block" : "none";
    departmentSelect.required = isFaculty;

    if (isFaculty) {
        loadFacultyDepartments();
    } else {
        departmentRequestId += 1;
        departmentSelect.disabled = true;
        departmentSelect.innerHTML = "<option value=''>Select a college and faculty role first</option>";
    }
}


// ==================================================
// LOAD STUDENTS
// ==================================================

async function loadStudents() {

    const tableBody =
        document.getElementById(
            "studentsTableBody"
        );

    try {

        const response =
            await fetch(
                "/api/users/students"
            );

        if (!response.ok) {

            throw new Error(
                "Student API error: " +
                response.status
            );

        }

        studentsData =
            await response.json();

        displayStudents(
            studentsData
        );

        updateCounts();

    }

    catch (error) {

        console.error(
            "Student Error:",
            error
        );

        tableBody.innerHTML = `
            <tr>
                <td colspan="5">
                    Unable to load students.
                </td>
            </tr>
        `;

    }

}


// ==================================================
// DISPLAY STUDENTS
// ==================================================

function displayStudents(students) {

    const tableBody =
        document.getElementById(
            "studentsTableBody"
        );

    tableBody.innerHTML = "";

    if (!students || students.length === 0) {

        tableBody.innerHTML = `
            <tr>
                <td colspan="5">
                    No students found.
                </td>
            </tr>
        `;

        return;
    }


    students.forEach(function (student) {

        tableBody.innerHTML += `
            <tr>

                <td>
                    ${escapeHtml(student.id)}
                </td>

                <td>
                    ${escapeHtml(student.name)}
                </td>

                <td>
                    ${escapeHtml(student.email)}
                </td>

                <td>
                    ${escapeHtml(student.college)}
                </td>

                <td>

                    <div class="action-buttons">

                        <button
                            type="button"
                            class="edit-btn"
                            onclick="editUser(
                                ${Number(student.id)},
                                '${escapeValue(student.name)}',
                                '${escapeValue(student.email)}',
                                '${escapeValue(student.college)}'
                            )"
                        >
                            ✏️ Edit
                        </button>

                        <button
                            type="button"
                            class="manage-portal-btn"
                            onclick="startAdminRolePortal(${Number(student.id)}, 'student')"
                        >
                            Manage Portal
                        </button>

                        <button
                            type="button"
                            class="delete-btn"
                            onclick="deleteUser(${Number(student.id)})"
                        >
                            🗑️ Delete
                        </button>

                    </div>

                </td>

            </tr>
        `;

    });

}


// ==================================================
// LOAD FACULTY
// ==================================================

async function loadFaculty() {

    const tableBody =
        document.getElementById(
            "facultyTableBody"
        );

    try {

        const response =
            await fetch(
                "/api/users/faculty"
            );

        if (!response.ok) {

            throw new Error(
                "Faculty API error: " +
                response.status
            );

        }

        facultyData =
            await response.json();

        displayFaculty(
            facultyData
        );

        updateCounts();

    }

    catch (error) {

        console.error(
            "Faculty Error:",
            error
        );

        tableBody.innerHTML = `
            <tr>
                <td colspan="5">
                    Unable to load faculty.
                </td>
            </tr>
        `;

    }

}


// ==================================================
// DISPLAY FACULTY
// ==================================================

function displayFaculty(faculty) {

    const tableBody =
        document.getElementById(
            "facultyTableBody"
        );

    tableBody.innerHTML = "";

    if (!faculty || faculty.length === 0) {

        tableBody.innerHTML = `
            <tr>
                <td colspan="5">
                    No faculty found.
                </td>
            </tr>
        `;

        return;
    }


    faculty.forEach(function (member) {

        tableBody.innerHTML += `
            <tr>

                <td>
                    ${escapeHtml(member.id)}
                </td>

                <td>
                    ${escapeHtml(member.name)}
                </td>

                <td>
                    ${escapeHtml(member.email)}
                </td>

                <td>
                    ${escapeHtml(member.college)}
                </td>

                <td>

                    <div class="action-buttons">

                        <button
                            type="button"
                            class="edit-btn"
                            onclick="editUser(
                                ${Number(member.id)},
                                '${escapeValue(member.name)}',
                                '${escapeValue(member.email)}',
                                '${escapeValue(member.college)}'
                            )"
                        >
                            ✏️ Edit
                        </button>

                        <button
                            type="button"
                            class="manage-portal-btn"
                            onclick="startAdminRolePortal(${Number(member.id)}, 'faculty')"
                        >
                            Manage Portal
                        </button>

                        <button
                            type="button"
                            class="delete-btn"
                            onclick="deleteUser(${Number(member.id)})"
                        >
                            🗑️ Delete
                        </button>

                    </div>

                </td>

            </tr>
        `;

    });

}


// ==================================================
// UPDATE COUNTS
// ==================================================

function updateCounts() {

    document.getElementById(
        "studentCount"
    ).textContent =
        studentsData.length;


    document.getElementById(
        "facultyCount"
    ).textContent =
        facultyData.length;


    document.getElementById(
        "totalUserCount"
    ).textContent =
        studentsData.length +
        facultyData.length;

}


// ==================================================
// OTHER COLLEGE SHOW / HIDE
// ==================================================

document
    .getElementById("userCollege")
    .addEventListener(
        "change",
        function () {

            const otherBox =
                document.getElementById(
                    "otherCollegeBox"
                );

            const createButton =
                document.getElementById(
                    "createUserBtn"
                );

            const otherName =
                document.getElementById(
                    "otherCollegeName"
                );

            const otherCity =
                document.getElementById(
                    "otherCollegeCity"
                );

            const requestStatus =
                document.getElementById(
                    "requestStatus"
                );


            if (this.value === "OTHER") {

                otherBox.style.display =
                    "grid";

                otherName.required =
                    true;

                otherCity.required =
                    true;

                createButton.style.display =
                    "none";

                requestStatus.style.display =
                    "none";

            }

            else {

                otherBox.style.display =
                    "none";

                otherName.required =
                    false;

                otherCity.required =
                    false;

                createButton.style.display =
                    "block";

                requestStatus.style.display =
                    "none";

            }

            if (document.getElementById("userRole").value === "faculty") {
                loadFacultyDepartments();
            } else if (document.getElementById("userRole").value === "student") {
                loadStudentClasses();
            }

        }
    );


document
    .getElementById("userRole")
    .addEventListener("change", function () {
        updateFacultyDepartmentField();
        updateStudentClassFields();
    });


// ==================================================
// REQUEST NEW COLLEGE
// ==================================================

document
    .getElementById(
        "requestCollegeBtn"
    )
    .addEventListener(
        "click",
        async function () {

            const collegeName =
                document
                    .getElementById(
                        "otherCollegeName"
                    )
                    .value
                    .trim();


            const city =
                document
                    .getElementById(
                        "otherCollegeCity"
                    )
                    .value
                    .trim();


            const name =
                document
                    .getElementById(
                        "userName"
                    )
                    .value
                    .trim();


            const email =
                document
                    .getElementById(
                        "userEmail"
                    )
                    .value
                    .trim();


            const status =
                document.getElementById(
                    "requestStatus"
                );


            const button =
                this;


            if (!collegeName || !city) {

                alert(
                    "Please enter college name and city."
                );

                return;
            }


            button.disabled = true;

            button.textContent =
                "Sending Request...";


            try {

                const response =
                    await fetch(
                        "/api/college-requests",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({

                                collegeName:
                                    collegeName,

                                city:
                                    city,

                                requestedBy:
                                    name || "User",

                                requestedEmail:
                                    email || ""

                            })
                        }
                    );


                const result =
                    await response.json();


                if (!response.ok) {

                    alert(
                        result.message ||
                        "Unable to send request."
                    );

                    return;
                }


                status.style.display =
                    "block";

                status.textContent =
                    "✅ Request sent successfully. Admin approval is required before this college can be used.";


                document
                    .getElementById(
                        "otherCollegeName"
                    )
                    .value = "";


                document
                    .getElementById(
                        "otherCollegeCity"
                    )
                    .value = "";


                await loadCollegeRequests();

            }

            catch (error) {

                console.error(
                    "College Request Error:",
                    error
                );

                alert(
                    "Unable to connect to server."
                );

            }

            finally {

                button.disabled =
                    false;

                button.textContent =
                    "📩 Send Request to Admin";

            }

        }
    );


// ==================================================
// LOAD COLLEGE REQUESTS
// ==================================================

async function loadCollegeRequests() {

    const tableBody =
        document.getElementById(
            "collegeRequestsTableBody"
        );

    try {

        const response =
            await fetch(
                "/api/college-requests"
            );


        if (!response.ok) {

            throw new Error(
                "Request API error: " +
                response.status
            );

        }


        collegeRequestsData =
            await response.json();


        displayCollegeRequests(
            collegeRequestsData
        );

    }

    catch (error) {

        console.error(
            "College Requests Error:",
            error
        );

        tableBody.innerHTML = `
            <tr>
                <td colspan="7">
                    Unable to load college requests.
                </td>
            </tr>
        `;

    }

}


// ==================================================
// DISPLAY COLLEGE REQUESTS
// ==================================================

function displayCollegeRequests(requests) {

    const tableBody =
        document.getElementById(
            "collegeRequestsTableBody"
        );

    tableBody.innerHTML = "";


    if (!requests || requests.length === 0) {

        tableBody.innerHTML = `
            <tr>
                <td colspan="7">
                    No college registration requests.
                </td>
            </tr>
        `;

        return;
    }


    requests.forEach(function (item) {

        let statusBadge = "";

        let actionButtons = "-";


        // STATUS

        if (item.status === "Pending") {

            statusBadge = `
                <span class="request-badge pending-badge">
                    Pending
                </span>
            `;

            actionButtons = `
                <div class="action-buttons">

                    <button
                        type="button"
                        class="approve-btn"
                        onclick="approveCollege(${Number(item.id)})"
                    >
                        ✅ Approve
                    </button>

                    <button
                        type="button"
                        class="reject-btn"
                        onclick="rejectCollege(${Number(item.id)})"
                    >
                        ❌ Reject
                    </button>

                </div>
            `;

        }

        else if (item.status === "Approved") {

            statusBadge = `
                <span class="request-badge approved-badge">
                    Approved
                </span>
            `;

            actionButtons = `
                <span>
                    Code:
                    <strong>
                        ${escapeHtml(item.collegeCode || "-")}
                    </strong>
                </span>
            `;

        }

        else {

            statusBadge = `
                <span class="request-badge rejected-badge">
                    Rejected
                </span>
            `;

        }


        tableBody.innerHTML += `
            <tr>

                <td>
                    ${escapeHtml(item.id)}
                </td>

                <td>
                    ${escapeHtml(item.collegeName)}
                </td>

                <td>
                    ${escapeHtml(item.city)}
                </td>

                <td>
                    ${escapeHtml(item.requestedBy)}
                </td>

                <td>
                    ${escapeHtml(item.createdAt)}
                </td>

                <td>
                    ${statusBadge}
                </td>

                <td>
                    ${actionButtons}
                </td>

            </tr>
        `;

    });

}


// ==================================================
// APPROVE COLLEGE
// ==================================================

async function approveCollege(id) {

    const confirmApprove =
        confirm(
            "Approve this college and add it to the official college list?"
        );


    if (!confirmApprove) {
        return;
    }


    try {

        const response =
            await fetch(
                `/api/college-requests/${id}/approve`,
                {
                    method: "POST"
                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            alert(
                result.message ||
                "Unable to approve college."
            );

            return;
        }


        alert(
            "✅ College approved successfully!\n\nCollege Code: " +
            (result.collegeCode || "Generated")
        );


        // Refresh request table

        await loadCollegeRequests();

        // IMPORTANT:
        // Approved college now appears in dropdown

        await loadColleges();

    }

    catch (error) {

        console.error(
            "Approve Error:",
            error
        );

        alert(
            "Unable to connect to server."
        );

    }

}


// ==================================================
// REJECT COLLEGE
// ==================================================

async function rejectCollege(id) {

    const confirmReject =
        confirm(
            "Are you sure you want to reject this college request?"
        );


    if (!confirmReject) {
        return;
    }


    try {

        const response =
            await fetch(
                `/api/college-requests/${id}/reject`,
                {
                    method: "POST"
                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            alert(
                result.message ||
                "Unable to reject request."
            );

            return;
        }


        alert(
            "❌ College request rejected."
        );


        await loadCollegeRequests();

    }

    catch (error) {

        console.error(
            "Reject Error:",
            error
        );

        alert(
            "Unable to connect to server."
        );

    }

}


// ==================================================
// SEARCH STUDENTS
// ==================================================

document
    .getElementById("studentSearch")
    .addEventListener(
        "input",
        function () {

            const search =
                this.value
                    .toLowerCase()
                    .trim();


            const filtered =
                studentsData.filter(
                    function (student) {

                        return (

                            String(student.name || "")
                                .toLowerCase()
                                .includes(search)

                            ||

                            String(student.email || "")
                                .toLowerCase()
                                .includes(search)

                        );

                    }
                );


            displayStudents(
                filtered
            );

        }
    );


// ==================================================
// SEARCH FACULTY
// ==================================================

document
    .getElementById("facultySearch")
    .addEventListener(
        "input",
        function () {

            const search =
                this.value
                    .toLowerCase()
                    .trim();


            const filtered =
                facultyData.filter(
                    function (member) {

                        return (

                            String(member.name || "")
                                .toLowerCase()
                                .includes(search)

                            ||

                            String(member.email || "")
                                .toLowerCase()
                                .includes(search)

                        );

                    }
                );


            displayFaculty(
                filtered
            );

        }
    );


// ==================================================
// REFRESH STUDENTS
// ==================================================

document
    .getElementById(
        "refreshStudents"
    )
    .addEventListener(
        "click",
        loadStudents
    );


// ==================================================
// REFRESH FACULTY
// ==================================================

document
    .getElementById(
        "refreshFaculty"
    )
    .addEventListener(
        "click",
        loadFaculty
    );


// ==================================================
// REFRESH COLLEGE REQUESTS
// ==================================================

document
    .getElementById(
        "refreshCollegeRequests"
    )
    .addEventListener(
        "click",
        loadCollegeRequests
    );


// ==================================================
// VIEW STUDENTS
// ==================================================

document
    .getElementById(
        "viewStudents"
    )
    .addEventListener(
        "click",
        function () {

            document
                .getElementById(
                    "studentsTableBody"
                )
                .scrollIntoView({
                    behavior: "smooth"
                });

        }
    );


// ==================================================
// VIEW FACULTY
// ==================================================

document
    .getElementById(
        "viewFaculty"
    )
    .addEventListener(
        "click",
        function () {

            document
                .getElementById(
                    "facultyTableBody"
                )
                .scrollIntoView({
                    behavior: "smooth"
                });

        }
    );


// ==================================================
// OPEN ADD USER
// ==================================================

document
    .getElementById(
        "openAddUser"
    )
    .addEventListener(
        "click",
        function () {

            document
                .getElementById(
                    "addUserSection"
                )
                .scrollIntoView({
                    behavior: "smooth"
                });

        }
    );


// ==================================================
// SHOW / HIDE PASSWORD
// ==================================================

document
    .getElementById(
        "togglePassword"
    )
    .addEventListener(
        "click",
        function () {

            const passwordInput =
                document.getElementById(
                    "userPassword"
                );


            if (
                passwordInput.type ===
                "password"
            ) {

                passwordInput.type =
                    "text";

                this.textContent =
                    "🙈";

                this.title =
                    "Hide password";

            }

            else {

                passwordInput.type =
                    "password";

                this.textContent =
                    "👁️";

                this.title =
                    "Show password";

            }

        }
    );


// ==================================================
// ADD USER
// ==================================================

document
    .getElementById(
        "addUserForm"
    )
    .addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();


            const name =
                document
                    .getElementById(
                        "userName"
                    )
                    .value
                    .trim();


            const email =
                document
                    .getElementById(
                        "userEmail"
                    )
                    .value
                    .trim();


            const college =
                document
                    .getElementById(
                        "userCollege"
                    )
                    .value;


            const role =
                document
                    .getElementById(
                        "userRole"
                    )
                    .value;

            const departmentId =
                document
                    .getElementById("facultyDepartment")
                    .value;

            const studentClassId =
                document.getElementById("studentClass").value;

            const rollNumber =
                document.getElementById("studentRollNumber").value.trim();


            const password =
                document
                    .getElementById(
                        "userPassword"
                    )
                    .value;


            // Do not allow OTHER to reach
            // normal user creation

            if (college === "OTHER") {

                alert(
                    "Please send the college registration request first."
                );

                return;
            }

            if (role === "faculty" && !departmentId) {
                alert("Please select an active department for the faculty account.");
                return;
            }

            if (role === "student" && (!studentClassId || !rollNumber)) {
                alert("Please select a class and enter the student's roll number.");
                return;
            }


            try {

                const response =
                    await fetch(
                        "/api/users/add",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body:
                                JSON.stringify({

                                    name:
                                        name,

                                    email:
                                        email,

                                    college:
                                        college,

                                    role:
                                        role,

                                    department_id:
                                        role === "faculty"
                                            ? Number(departmentId)
                                            : null,

                                    class_id:
                                        role === "student"
                                            ? Number(studentClassId)
                                            : null,

                                    roll_number:
                                        role === "student"
                                            ? rollNumber
                                            : null,

                                    password:
                                        password

                                })

                        }
                    );


                const result =
                    await response.json();


                if (!response.ok) {

                    alert(
                        result.message ||
                        "Unable to create user."
                    );

                    return;
                }


                alert(
                    "✅ User created successfully!"
                );


                document
                    .getElementById(
                        "addUserForm"
                    )
                    .reset();

                updateFacultyDepartmentField();
                updateStudentClassFields();


                document
                    .getElementById(
                        "userPassword"
                    )
                    .type =
                    "password";


                document
                    .getElementById(
                        "togglePassword"
                    )
                    .textContent =
                    "👁️";


                document
                    .getElementById(
                        "otherCollegeBox"
                    )
                    .style.display =
                    "none";


                await loadStudents();

                await loadFaculty();

            }

            catch (error) {

                console.error(
                    "Add User Error:",
                    error
                );

                alert(
                    "Unable to connect to server."
                );

            }

        }
    );


document
    .getElementById("departmentCollege")
    .addEventListener("change", function () {
        document.getElementById("departmentStatus").textContent = "";
        loadManagedDepartments();
    });

document
    .getElementById("refreshDepartments")
    .addEventListener("click", loadManagedDepartments);

document
    .getElementById("departmentForm")
    .addEventListener("submit", async function (event) {
        event.preventDefault();

        const form = this;
        const submitButton = document.getElementById("createDepartmentBtn");
        const status = document.getElementById("departmentStatus");
        const collegeCode = document.getElementById("departmentCollege").value;

        status.textContent = "";
        submitButton.disabled = true;

        try {
            const response = await fetch("/api/departments", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    college_code: collegeCode,
                    name: document.getElementById("departmentName").value.trim(),
                    code: document.getElementById("departmentCode").value.trim(),
                    is_active: document.getElementById("departmentActive").checked
                })
            });
            const result = await response.json();

            if (!response.ok || !result.success) {
                throw new Error(result.message || "Unable to create department.");
            }

            const currentCollege = collegeCode;
            form.reset();
            document.getElementById("departmentCollege").value = currentCollege;
            status.textContent = result.message || "Department created successfully.";
            await loadManagedDepartments();

            if (
                document.getElementById("userRole").value === "faculty"
                && document.getElementById("userCollege").value === currentCollege
            ) {
                await loadFacultyDepartments();
            }
        } catch (error) {
            status.textContent = error.message || "Unable to create department.";
        } finally {
            submitButton.disabled = false;
        }
    });


// ==================================================
// EDIT USER
// ==================================================

async function editUser(
    id,
    currentName,
    currentEmail,
    currentCollege
) {

    const name =
        prompt(
            "Enter new name:",
            currentName
        );


    if (name === null) {
        return;
    }


    const email =
        prompt(
            "Enter new email:",
            currentEmail
        );


    if (email === null) {
        return;
    }


    const college =
        prompt(
            "Enter official college code:",
            currentCollege
        );


    if (college === null) {
        return;
    }


    if (
        name.trim() === "" ||
        email.trim() === "" ||
        college.trim() === ""
    ) {

        alert(
            "Please fill all fields."
        );

        return;
    }


    try {

        const response =
            await fetch(
                `/api/users/edit/${id}`,
                {
                    method: "PUT",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({

                            name:
                                name.trim(),

                            email:
                                email.trim(),

                            college:
                                college.trim()

                        })

                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            alert(
                result.message ||
                "Unable to update user."
            );

            return;
        }


        alert(
            "✅ User updated successfully!"
        );


        await loadStudents();

        await loadFaculty();

    }

    catch (error) {

        console.error(
            "Edit User Error:",
            error
        );

        alert(
            "Unable to connect to server."
        );

    }

}


// ==================================================
// DELETE USER
// ==================================================

async function deleteUser(id) {

    const confirmDelete =
        confirm(
            "Are you sure you want to delete this user?"
        );


    if (!confirmDelete) {
        return;
    }


    try {

        const response =
            await fetch(
                `/api/users/delete/${id}`,
                {
                    method: "DELETE"
                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            alert(
                result.message ||
                "Unable to delete user."
            );

            return;
        }


        alert(
            "✅ User deleted successfully!"
        );


        await loadStudents();

        await loadFaculty();

    }

    catch (error) {

        console.error(
            "Delete Error:",
            error
        );

        alert(
            "Unable to connect to server."
        );

    }

}


// ==================================================
// INITIAL LOAD
// ==================================================

loadColleges();


async function startAdminRolePortal(userId, role) {
    const roleName = role === "student" ? "Student" : "Faculty";
    if (!Number.isInteger(userId) || userId <= 0 || !["student", "faculty"].includes(role)) {
        window.alert("Choose a valid Student or Faculty account.");
        return;
    }

    try {
        const response = await fetch("/api/admin/manage-user", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId, role })
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || `Unable to open the ${roleName} portal.`);
        }
        window.location.assign(result.redirect || `/${role}-dashboard.html`);
    } catch (error) {
        window.alert(error.message || `Unable to open the ${roleName} portal.`);
    }
}

loadStudents();

loadFaculty();

loadCollegeRequests();
