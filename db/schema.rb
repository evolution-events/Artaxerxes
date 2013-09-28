# encoding: UTF-8
# This file is auto-generated from the current state of the database. Instead
# of editing this file, please use the migrations feature of Active Record to
# incrementally modify your database, and then regenerate this schema definition.
#
# Note that this schema.rb definition is the authoritative source for your
# database schema. If you need to create the application database on another
# system, you should be using db:schema:load, not running all the migrations
# from scratch. The latter is a flawed and unsustainable approach (the more migrations
# you'll amass, the slower it'll run and the greater likelihood for issues).
#
# It's strongly recommended that you check this file into your version control system.

ActiveRecord::Schema.define(version: 20130928202406) do

  create_table "emergency_contacts", force: true do |t|
    t.string   "name"
    t.string   "relation"
    t.string   "phone_number"
    t.text     "remarks"
    t.integer  "user_id"
    t.datetime "created_at"
    t.datetime "updated_at"
  end

  add_index "emergency_contacts", ["user_id"], name: "index_emergency_contacts_on_user_id"

  create_table "events", force: true do |t|
    t.string   "name"
    t.string   "title"
    t.date     "start_date"
    t.date     "end_date"
    t.string   "location_name"
    t.text     "location_info"
    t.text     "description"
    t.string   "url"
    t.integer  "series_id"
    t.datetime "created_at"
    t.datetime "updated_at"
  end

  create_table "medical_details", force: true do |t|
    t.string   "name"
    t.string   "type"
    t.text     "description"
    t.integer  "user_id"
    t.datetime "created_at"
    t.datetime "updated_at"
  end

  create_table "series", force: true do |t|
    t.string   "name"
    t.string   "url"
    t.datetime "created_at"
    t.datetime "updated_at"
  end

  create_table "user_addresses", force: true do |t|
    t.string   "address"
    t.string   "postal_code"
    t.string   "city"
    t.string   "country"
    t.integer  "user_id"
    t.datetime "created_at"
    t.datetime "updated_at"
  end

  create_table "users", force: true do |t|
    t.string   "first_name"
    t.string   "preposition"
    t.string   "last_name"
    t.string   "username"
    t.date     "birthdate"
    t.string   "phone_number"
    t.string   "email"
    t.string   "gender"
    t.boolean  "hide_last_name"
    t.datetime "created_at"
    t.datetime "updated_at"
  end

end
